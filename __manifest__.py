{
    'name': 'Product REST API',
    'version': '18.0.1.0.0',
    'category': 'API',
    'summary': 'RESTful API for products with stock and pricing information',
    'description': """
        This module provides RESTful API endpoints for:
        - Retrieving product lists with on-hand quantities and pricing
        - Getting detailed product information
        - Stock information by location

        Compatible with Odoo 18 Community Edition
    """,
    'author': 'Shahriar Ahmed - BJIT Limited',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'mail', 'product', 'stock', 'sale', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/vehicle_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}