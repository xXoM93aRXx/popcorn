# -*- coding: utf-8 -*-

import json
import base64
import logging
from odoo import http, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class PopcornSignatureController(http.Controller):
    
    @http.route('/popcorn/signature/capture/<int:document_id>', type='http', auth='user', website=True)
    def signature_capture_page(self, document_id, **kwargs):
        """Display signature capture page"""
        document = request.env['popcorn.signature.document'].browse(document_id)
        
        # Check if document exists and user has access
        if not document.exists():
            return request.not_found()
        
        # Get or create signature template
        template = request.env['popcorn.signature.template'].search([
            ('document_type', '=', document.document_type),
            ('active', '=', True)
        ], limit=1)
        
        if not template:
            # Create default template if none exists
            template = request.env['popcorn.signature.template'].create({
                'name': f'Default {document.document_type.replace("_", " ").title()} Template',
                'document_type': document.document_type,
                'header_text': 'Please sign below:',
                'footer_text': 'By signing this document, you agree to the terms and conditions.'
            })
        
        template_config = template.get_template_config()
        
        values = {
            'document': document,
            'template': template,
            'template_config': json.dumps(template_config),
            'page_title': f'Sign Document: {document.name}'
        }
        
        return request.render('popcorn.signature_capture_template', values)
    
    @http.route('/popcorn/signature/save', type='json', auth='user', methods=['POST'])
    def save_signature(self, document_id, signature_data, signature_image=None, **kwargs):
        """Save signature data to document"""
        try:
            document = request.env['popcorn.signature.document'].browse(document_id)
            
            if not document.exists():
                return {'success': False, 'message': 'Document not found'}
            
            # Get request information
            ip_address = request.httprequest.environ.get('REMOTE_ADDR')
            user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')
            
            # Save signature
            document.sign_document(
                signature_data=signature_data,
                signature_image=signature_image,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return {
                'success': True,
                'message': 'Signature saved successfully',
                'document_id': document.id,
                'signed_date': document.signed_date.isoformat() if document.signed_date else None
            }
            
        except Exception as e:
            _logger.error(f"Error saving signature: {str(e)}")
            return {'success': False, 'message': 'Error saving signature'}
    
    @http.route('/popcorn/signature/clear', type='json', auth='user', methods=['POST'])
    def clear_signature(self, document_id, **kwargs):
        """Clear signature from document"""
        try:
            document = request.env['popcorn.signature.document'].browse(document_id)
            
            if not document.exists():
                return {'success': False, 'message': 'Document not found'}
            
            document.write({
                'signature_data': False,
                'signature_image': False,
                'signature_filename': False,
                'signed_date': False,
                'signed_by': False,
                'state': 'draft'
            })
            
            return {'success': True, 'message': 'Signature cleared successfully'}
            
        except Exception as e:
            _logger.error(f"Error clearing signature: {str(e)}")
            return {'success': False, 'message': 'Error clearing signature'}
    
    @http.route('/popcorn/signature/document/create', type='json', auth='user', methods=['POST'])
    def create_signature_document(self, partner_id, document_type='general', event_id=None, membership_id=None, name=None, **kwargs):
        """Create a new signature document"""
        try:
            document = request.env['popcorn.signature.document'].create_signature_document(
                partner_id=partner_id,
                document_type=document_type,
                event_id=event_id,
                membership_id=membership_id,
                name=name
            )
            
            return {
                'success': True,
                'document_id': document.id,
                'message': 'Signature document created successfully'
            }
            
        except Exception as e:
            _logger.error(f"Error creating signature document: {str(e)}")
            return {'success': False, 'message': 'Error creating signature document'}
    
    @http.route('/popcorn/signature/document/<int:document_id>/status', type='json', auth='user')
    def get_document_status(self, document_id, **kwargs):
        """Get document signature status"""
        try:
            document = request.env['popcorn.signature.document'].browse(document_id)
            
            if not document.exists():
                return {'success': False, 'message': 'Document not found'}
            
            return {
                'success': True,
                'document': {
                    'id': document.id,
                    'name': document.name,
                    'state': document.state,
                    'signed_date': document.signed_date.isoformat() if document.signed_date else None,
                    'has_signature': bool(document.signature_data or document.signature_image),
                    'partner_name': document.partner_id.name,
                    'document_type': document.document_type
                }
            }
            
        except Exception as e:
            _logger.error(f"Error getting document status: {str(e)}")
            return {'success': False, 'message': 'Error getting document status'}
    
    @http.route('/popcorn/signature/document/<int:document_id>/image', type='http', auth='user')
    def get_signature_image(self, document_id, **kwargs):
        """Get signature image"""
        try:
            document = request.env['popcorn.signature.document'].browse(document_id)
            
            if not document.exists() or not document.signature_image:
                return request.not_found()
            
            return request.make_response(
                base64.b64decode(document.signature_image),
                headers=[
                    ('Content-Type', 'image/png'),
                    ('Content-Disposition', f'attachment; filename={document.signature_filename or "signature.png"}')
                ]
            )
            
        except Exception as e:
            _logger.error(f"Error getting signature image: {str(e)}")
            return request.not_found()


class PopcornSignaturePortal(CustomerPortal):
    
    def _prepare_home_portal_values(self, counters):
        """Add signature document count to portal home"""
        values = super()._prepare_home_portal_values(counters)
        
        if 'signature_count' in counters:
            partner = request.env.user.partner_id
            signature_count = request.env['popcorn.signature.document'].search_count([
                ('partner_id', '=', partner.id)
            ])
            values['signature_count'] = signature_count
        
        return values
    
    @http.route(['/my/signatures', '/my/signatures/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_signatures(self, page=1, **kw):
        """Display user's signature documents in portal"""
        partner = request.env.user.partner_id
        signature_documents = request.env['popcorn.signature.document'].search([
            ('partner_id', '=', partner.id)
        ])
        
        # Pagination
        pager = request.website.pager(
            url="/my/signatures",
            url_args={},
            total=len(signature_documents),
            page=page,
            step=10
        )
        
        paged_documents = signature_documents[(page - 1) * 10:page * 10]
        
        values = {
            'documents': paged_documents,
            'pager': pager,
            'page_name': 'signatures',
        }
        
        return request.render("popcorn.portal_my_signatures", values)
