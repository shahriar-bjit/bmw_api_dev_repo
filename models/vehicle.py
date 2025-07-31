from odoo import fields, models

class Vehicle(models.Model):
    _name = 'vehicle.management'
    _description = 'Vehicle Management and Description'

    vehicle_name = fields.Char(string='Vehicle Name', required=True)
    registration_number = fields.Char(string='Registration Number', required=True)
    model = fields.Char(string='Model')
    registration_year = fields.Char(string='Registration Year')
    colour = fields.Char(string='Colour')
    owner_id = fields.Many2one('res.partner', string='Owner')

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vehicle_ids = fields.One2many('vehicle.management', 'owner_id', string='Vehicles', ondelete='cascade')