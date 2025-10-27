# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PopcornProfileController(http.Controller):
    """Controller for user profile management"""
    
    @http.route(['/my/profile'], type='http', auth="user", website=True)
    def profile_edit(self, **kwargs):
        """Display the profile edit page"""
        partner = request.env.user.partner_id
        
        # Get available options for dropdowns
        mbti_options = partner._fields['mbti'].selection if partner._fields.get('mbti') else []
        gender_options = partner._fields['gender'].selection if partner._fields.get('gender') else []
        zodiac_options = partner._fields['zodiac'].selection if partner._fields.get('zodiac') else []
        
        # Get available topics (event tags where category name contains "Topic")
        topics = request.env['event.tag'].search([
            ('category_id.name', 'ilike', 'Topic')
        ])
        
        # Get available activities & sports grouped by category
        activities_sports = request.env['popcorn.activity_sport'].search([
            ('active', '=', True)
        ], order='category_id, name')
        
        # Group by category
        activities_by_category = {}
        for activity in activities_sports:
            category_name = activity.category_id.name if activity.category_id else 'Other'
            if category_name not in activities_by_category:
                activities_by_category[category_name] = []
            activities_by_category[category_name].append(activity)
        
        values = {
            'partner': partner,
            'mbti_options': mbti_options,
            'gender_options': gender_options,
            'zodiac_options': zodiac_options,
            'available_topics': topics,
            'activities_by_category': activities_by_category,
        }
        
        return request.render('popcorn.popcorn_profile_edit_page', values)
    
    @http.route(['/my/profile/update'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def profile_update(self, **kwargs):
        """Update the user's profile information"""
        partner = request.env.user.partner_id
        
        try:
            # Get form data
            form_data = request.httprequest.form
            
            # Prepare update values
            update_vals = {}
            
            # Update single-select fields
            if 'mbti' in kwargs:
                update_vals['mbti'] = kwargs['mbti']
            
            if 'gender' in kwargs:
                update_vals['gender'] = kwargs['gender']
            
            if 'zodiac' in kwargs:
                update_vals['zodiac'] = kwargs['zodiac']
            
            # Update many2many fields using getlist
            topic_ids = [int(id) for id in form_data.getlist('preferred_topics') if id]
            activity_ids = [int(id) for id in form_data.getlist('activities_sports') if id]
            
            update_vals['preferred_topics'] = [(6, 0, topic_ids)] if topic_ids else [(5, 0, 0)]
            update_vals['activities_sports'] = [(6, 0, activity_ids)] if activity_ids else [(5, 0, 0)]
            
            # Update the partner
            if update_vals:
                partner.write(update_vals)
            
            # Return success
            return request.redirect('/my/profile?success=1')
            
        except Exception as e:
            _logger.error("Error updating profile: %s", str(e))
            return request.redirect('/my/profile?error=Unable to update profile. Please try again.')

