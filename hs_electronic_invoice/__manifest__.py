# -*- coding: utf-8 -*-
{
    "name": "hs_electronic_invoice",
    "summary": """
       Electronic Invoice""",
    "description": """
        Long description of module's purpose
    """,
    "author": "HS Consult",
    "website": "http://www.hconsul.com/odoo/",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    "category": "Uncategorized",
    "version": "0.1",
    "licence": "OPL-1",
    # any module necessary for this one to work correctly
    "depends": ["base", "account_accountant"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/views.xml",
        "views/views_fe_moves.xml",
        "views/views_fe_logs.xml",
         "views/views_fe_cpbs.xml",
        "views/fe_invoice.xml",
        "views/templates.xml",
        "views/views_product_field.xml",
        "views/views_product_variants_field.xml",
        "views/views_customers_field.xml",
    ],
    # only loaded in demonstration mode
    "demo": [
        "demo/demo.xml",
    ],
    "installable": True,
    "auto_install": False,
}
