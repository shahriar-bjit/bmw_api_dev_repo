from odoo import api, models, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.onchange('default_code')
    def _onchange_default_code_changed(self):
        if not self.default_code:
            return

        domain = [('default_code', '=', self.default_code)]
        if self.id:
            domain.append(('id', '!=', self.id))

        if self.env['product.template'].search_count(domain, limit=1):
            duplicate = self.default_code
            # Use _origin to revert to saved value
            self.default_code = self._origin.default_code

            return {
                'warning': {
                    'title': _("Duplicate Reference Code"),
                    'message': _(
                        "The Reference '%s' already exists. Reverted to the original value."
                    ) % duplicate,
                }
            }
