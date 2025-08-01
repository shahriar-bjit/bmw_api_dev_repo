from odoo import http
from odoo.http import request

class VehicleController(http.Controller):
    @http.route('/api/vehicle/create', type='json', auth='none', methods=['POST'], csrf=False, cors="*")
    def create_vehicle(self, **kwargs):
        try:
            name = kwargs.get('name')
            registration_number = kwargs.get('registration_number')
            owner_id = kwargs.get('owner_id')
            registration_year = kwargs.get('registration_year')
            colour = kwargs.get('colour')
            model = kwargs.get('model')

            if not name or not registration_number or not owner_id:
                return {'error': 'Required field missing'}, 400

            configured_key = request.env['ir.config_parameter'].sudo().get_param('api.product_access_key')
            token = request.httprequest.headers.get('X-API-Key')
            if token != configured_key:
                return {'error': 'Unauthorized'}, 401

            partner = request.env['res.partner'].sudo().browse(owner_id)
            if not partner.exists():
                return {'status': 'Failure', 'reason': 'Partner not found'}

            vehicle = request.env['vehicle.management'].sudo().create({
                'vehicle_name': name,
                'registration_number': registration_number,
                'model': model,
                'registration_year': registration_year,
                'colour': colour,
                'owner_id': owner_id,
            })

            return {'status': 'Success', 'vehicle_id': vehicle.id}
        except Exception as e:
            return {'error': str(e)}, 500

    @http.route('/api/vehicle/delete', type='json', auth='none', methods=['DELETE'], csrf=False, cors="*")
    def delete_vehicle(self, **kwargs):
        try:
            registration_number = kwargs.get('registration_number')
            owner_id = kwargs.get('owner_id')

            if not registration_number or not owner_id:
                return {'error': 'Required field missing'}, 400

            configured_key = request.env['ir.config_parameter'].sudo().get_param('api.product_access_key')
            token = request.httprequest.headers.get('X-API-Key')
            if token != configured_key:
                return {'error': 'Unauthorized'}, 401

            vehicle = request.env['vehicle.management'].sudo().search([('registration_number', '=', registration_number), ('owner_id', '=', int(owner_id))], limit=1)

            if not vehicle:
                return {'status': 'Failure', 'reason': 'Vehicle not found'}, 404

            vehicle.unlink()

            return {'status': 'Success', 'message': 'Vehicle deleted successfully'}
        except Exception as e:
            return {'error': str(e)}, 500