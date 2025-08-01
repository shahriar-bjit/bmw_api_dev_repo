from odoo import fields, models, api

class Vehicle(models.Model):
    _name = 'vehicle.management'
    _description = 'Vehicle Management and Description'

    vehicle_name = fields.Char(string='Vehicle Name', required=True)
    registration_number = fields.Char(string='Registration Number', required=True)
    model = fields.Char(string='Model')
    registration_year = fields.Char(string='Registration Year')
    colour = fields.Char(string='Colour')
    owner_id = fields.Many2one('res.partner', string='Owner', ondelete='cascade')

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vehicle_ids = fields.One2many('vehicle.management', 'owner_id', string='Vehicles')
    has_vehicles = fields.Boolean(compute="_compute_has_vehicles")

    @api.depends('vehicle_ids')
    def _compute_has_vehicles(self):
        for rec in self:
            rec.has_vehicles = bool(rec.vehicle_ids)

    def action_open_vehicles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vehicles',
            'res_model': 'vehicle.management',
            'view_mode': 'list,form',
            'domain': [('owner_id', '=', self.id)],
            'context': {'default_owner_id': self.id},
        }