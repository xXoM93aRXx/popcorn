from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class PopcornReferralController(http.Controller):
    
    @http.route('/popcorn/event/<int:event_id>/referral/<string:referral_code>', type='http', auth='public', website=True)
    def referral_landing(self, event_id, referral_code, **kwargs):
        """Redirect referral links directly to event registration page"""
        try:
            # Get the event
            event = request.env['event.event'].sudo().browse(event_id)
            
            if not event.exists():
                return request.redirect('/event')
            
            # Get the referral
            referral = request.env['popcorn.referral'].sudo().search([
                ('name', '=', referral_code),
                ('event_id', '=', event_id)
            ], limit=1)
            
            if not referral.exists():
                return request.redirect(f'/popcorn/event/{event.id}/register')
            
            # Check if referral is expired
            if referral.expiry_date and fields.Datetime.now() > referral.expiry_date:
                referral.status = 'expired'
                return request.redirect(f'/popcorn/event/{event.id}/register')
            
            # Store referral code in session for tracking and redirect to normal registration page
            request.session['referral_code'] = referral_code
            redirect_url = f'/popcorn/event/{event.id}/register?ref={referral_code}'
            return request.redirect(redirect_url)
            
        except Exception as e:
            _logger.error(f"Error in referral landing page: {str(e)}")
            return request.redirect('/event')
    
    @http.route('/popcorn/referral/generate', type='http', auth='user', methods=['POST'], csrf=False)
    def generate_referral_link(self, **kwargs):
        """Generate a referral link for the current user"""
        try:
            event_id = kwargs.get('event_id')
            if not event_id:
                return request.make_json_response({'success': False, 'error': 'Event ID is required'})
            
            # Convert string to int
            try:
                event_id = int(event_id)
            except (ValueError, TypeError):
                return request.make_json_response({'success': False, 'error': 'Invalid event ID'})
            
            event = request.env['event.event'].browse(event_id)
            if not event.exists():
                return request.make_json_response({'success': False, 'error': 'Event not found'})
            
            if not event.referral_prize or event.referral_prize <= 0:
                return request.make_json_response({'success': False, 'error': 'This event does not have a referral prize'})
            
            # Create referral
            referral = request.env['popcorn.referral'].sudo().create({
                'referrer_id': request.env.user.partner_id.id,
                'event_id': event_id,
                'referral_prize': event.referral_prize
            })
            
            return request.make_json_response({
                'success': True,
                'referral_link': referral.referral_link,
                'referral_code': referral.name,
                'prize_amount': event.referral_prize,
                'currency_symbol': event.currency_id.symbol
            })
            
        except Exception as e:
            _logger.error(f"Error generating referral link: {str(e)}")
            return request.make_json_response({'success': False, 'error': str(e)})
    
    
    @http.route('/popcorn/referral/validate', type='json', auth='user', methods=['POST'])
    def validate_referral_registration(self, registration_id, **kwargs):
        """Validate and process referral registration"""
        try:
            registration = request.env['event.registration'].browse(registration_id)
            if not registration.exists():
                return {'error': 'Registration not found'}
            
            # Check if there's a referral code in session
            referral_code = request.session.get('referral_code')
            if not referral_code:
                return {'success': True}  # No referral, normal registration
            
            # Process the referral
            referral = request.env['popcorn.referral'].process_referral_registration(
                referral_code=referral_code,
                referee_id=registration.partner_id.id,
                registration_id=registration.id
            )
            
            # Clear the referral code from session
            request.session.pop('referral_code', None)
            
            return {
                'success': True,
                'referral_processed': True,
                'referral_code': referral_code,
                'prize_amount': referral.referral_prize,
                'currency_symbol': registration.event_id.currency_id.symbol
            }
            
        except ValidationError as e:
            _logger.warning(f"Referral validation failed: {str(e)}")
            return {'error': str(e)}
        except Exception as e:
            _logger.error(f"Error validating referral: {str(e)}")
            return {'error': str(e)}
