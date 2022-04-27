# -*- coding: utf-8 -*-

import base64
from cmath import log
from io import BytesIO
from pydoc import cli
from odoo import models, fields, api
import zeep
import logging
from base64 import b64decode
from datetime import datetime, timezone
from odoo import http
from odoo.http import request
from odoo.http import content_disposition
import qrcode
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class electronic_invoice_fields(models.Model):
	_inherit = "account.move"
	lastFiscalNumber = fields.Char(
		string="Número Fiscal", compute="on_change_state", readonly="True", store="True")
	puntoFactFiscal = fields.Char(
		string="Punto Facturación Fiscal", readonly="True")
	pagadoCompleto = fields.Char(
		string="Estado de Pago", compute="on_change_pago", readonly="True", store="True")
	qr_code = fields.Binary("QR Factura Electrónica",
							attachment=True, readonly="True")
	tipo_documento_fe = fields.Selection(
		string='Tipo de Documento',
		selection=[
			('01', 'Factura de operación interna'),
			('02', 'Factura de importación'),
			('03', 'Factura de exportación'),
			('04', 'Nota de Crédito referente a una FE'),
			('05', 'Nota de Débito referente a una FE'),
			('06', 'Nota de Crédito genérica'),
			('07', 'Nota de Débito genérica'),
			('08', 'Factura de Zona Franca'),
			('09', 'Reembolso'),
		],
		default='01',
		help='Tipo de Documento para Factura Eletrónica.'
	)
	tipo_emision_fe = fields.Selection(
		string='Tipo de Emisión',
		selection=[
			('01', 'Autorización de Uso Previa, operación normal'),
			('02', 'Autorización de Uso Previa, operación en contingencia'),
			('03', 'Autorización de Uso Posterior, operación normal'),
			('04', ' Autorización de Uso posterior, operación en contingencia')
		],
		default='01',
		help='Tipo de Emisión para Factura Eletrónica.'
	)
	fecha_inicio_contingencia = fields.Date(
		string='Fecha Inicio de Contingencia')
	motivo_contingencia = fields.Char(string='Motivo de Contingencia')
	naturaleza_operacion_fe = fields.Selection(
		string='Naturaleza de Operación',
		selection=[
			('01', 'Venta'),
			('02', 'Exportación'),
			('10', 'Transferencia'),
			('11', 'Devolución'),
			('12', 'Consignación'),
			('13', 'Remesa'),
			('14', 'Entrega gratuita'),
			('20', 'Compra'),
			('21', 'Importación'),
		],
		default='01',
		help='Naturaleza de Operación para Factura Eletrónica.'
	)
	tipo_operacion_fe = fields.Selection(
		string='Tipo de Operación',
		selection=[
			('1', 'Salida o venta'),
			('2', 'Entrada o compra (factura de compra- para comercio informal. Ej.: taxista, trabajadores manuales)'),
		],
		default='1',
		help='Tipo de Operación para Factura Eletrónica.'
	)
	destino_operacion_fe = fields.Selection(
		string='Destino de Operación',
		selection=[
			('1', 'Panamá'),
			('2', 'Extranjero'),
		],
		default='1',
		help='Destino de Operación para Factura Eletrónica.'
	)
	formatoCAFE_fe = fields.Selection(
		string='Formato CAFE',
		selection=[
			('1', 'Sin generación de CAFE: El emisor podrá decidir generar CAFE en cualquier momento posterior a la autorización de uso de FE'),
			('2', 'Cinta de papel'),
			('3', 'Papel formato carta.'),
		],
		default='1',
		help='Formato CAFE Factura Eletrónica.'
	)
	entregaCAFE_fe = fields.Selection(
		string='Entrega CAFE',
		selection=[
			('1', 'Sin generación de CAFE: El emisor podrá decidir generar CAFE en cualquier momento posterior a la autorización de uso de FE'),
			('2', 'CAFE entregado para el receptor en papel'),
			('3', 'CAFE enviado para el receptor en formato electrónico'),
		],
		default='1',
		help='Entrega CAFE Factura Eletrónica.'
	)
	envioContenedor_fe = fields.Selection(
		string='Envío de Contenedor',
		selection=[
			('1', 'Normal'),
			('2', ' El receptor exceptúa al emisor de la obligatoriedad de envío del contenedor. El emisor podrá decidir entregar el contenedor, por cualquier razón, en momento posterior a la autorización de uso, pero no era esta su intención en el momento de la emisión de la FE.'),
		],
		default='1',
		help='Envío de Contenedor Eletrónica.'
	)
	procesoGeneracion_fe = fields.Selection(
		string='Proceso de Generación',
		selection=[
			('1', 'Generación por el sistema de facturación del contribuyente (desarrollo propio o producto adquirido)'),
		],
		default='1',
		readonly=True,
		help='Proceso de Generación de Factura Eletrónica.'
	)
	tipoVenta_fe = fields.Selection(
		string='Tipo de Venta',
		selection=[
			('1', 'Venta de Giro del negocio'),
			('2', 'Venta Activo Fijo'),
			('3', 'Venta de Bienes Raíces'),
			('4', 'Prestación de Servicio. Si no es venta, no informar este campo'),
		],
		default='1',
		help='Tipo de venta Factura Eletrónica.'
	)
	tipoSucursal_fe = fields.Selection(
		string='Tipo de Sucursal',
		selection=[
			('1', 'Mayor cantidad de Operaciones venta al detal (retail)'),
			('2', 'Mayor cantidad de Operaciones venta al por mayor')
		],
		default='1',
		help='Tipo de sucursal Eletrónica.'
	)

	# payment_referece_credit_note = fields.ManyToOne(string="Referencia de FE", )
	reversal_reason_fe = fields.Char(string='Reason', readonly="True")
	#reembolso = fields.Char(string = 'Reembolso', compute="on_change_payment_state", readonly = "True")
	anulado = fields.Char(string='Anulado', readonly="True", store="True")
	nota_credito = fields.Char(
		string='Nota de Crédito', readonly="True", compute="on_change_type",)
	total_precio_descuento = 0.0
	@api.depends('qr_code')
	def on_change_pago(self):
		for record in self:
			logging.info('Blank QR: ' + str(record.qr_code))
			# if str(record.amount_residual) == '0.0' and record.lastFiscalNumber:
			if str(record.qr_code) != "False":
				record.pagadoCompleto = 'FECompletada'
				# self.llamar_ebi_pac()
				#logging.info('Amoount Valor: ' + str(record.amount_residual))
			else:
				record.pagadoCompleto = 'Pendiente'

	@api.depends('state')
	def on_change_state(self):
		logging.info('Entró al onchange: ')
		for record in self:
			logging.info('HSInvoice: ' + str(record.amount_residual) +
						 ":" + str(record.lastFiscalNumber))
			if record.state == 'posted' and record.pagadoCompleto != "NumeroAsignado":
				record.pagadoCompleto = "NumeroAsignado"
				if record.lastFiscalNumber == False:
					#record.lastFiscalNumber = '000045'
					#first_id = self.env['electronic.invoice'].search([('payment_id','=',rec.invoice_payment_term_id.id)], order='days asc')[0].id
					document = self.env["electronic.invoice"].search(
						[('name', '=', 'ebi-pac')], limit=1)
					if document:
						fiscalN = (
							str(document.numeroDocumentoFiscal).rjust(10, '0'))
						puntoFacturacion = (
							str(document.puntoFacturacionFiscal).rjust(3, '0'))

						record.lastFiscalNumber = fiscalN
						record.puntoFactFiscal = puntoFacturacion

						document.numeroDocumentoFiscal = str(
							int(document.numeroDocumentoFiscal)+1)

	@api.depends('type', 'partner_id')
	def on_change_type(self):
		if self.type:
			logging.info('Entró a cambio type:' + str(self.type))
			logging.info('El residuo del monto:' + str(self.amount_residual))
			for record in self:
				if record.type == 'out_refund' and str(record.amount_residual) == "0.0":
					logging.info('Entró a Nota de Crédito: NCRFE - Anulación')
					record.tipo_documento_fe = "04"
					record.nota_credito = "NotaCredito"
				else:
					record.nota_credito = ""
					# and self.payment_state == "not_paid":
					if record.type == 'out_refund' and record.state == "draft" and record.reversed_entry_id.id != False:

						original_invoice_id = self.env["account.move"].search(
							[('id', '=', self.reversed_entry_id.id)], limit=1)
						if original_invoice_id:
							payment = original_invoice_id.amount_residual
							inv_monto_total = original_invoice_id.amount_total
							logging.info(
								"estos son los pagos!!!" + str(payment))
							if payment != inv_monto_total:  # and payment != "reversed":
								logging.info(
									'Entró a Nota de Crédito: Reembolso')
								record.tipo_documento_fe = "09"
								record.nota_credito = "Reembolso"
							else:
								logging.info(
									'Entró a Nota de Crédito: NCRFE PARCIAL.')
								self.tipo_documento_fe = "04"
								self.nota_credito = "NotaCredito"
					else:
						# and self.payment_state == "not_paid":
						if record.type == 'out_refund' and record.state == "draft" and record.reversed_entry_id.id == False:
							logging.info('Entró a Nota de Crédito: NCG')
							record.tipo_documento_fe = "06"
							record.nota_credito = "NotaCredito"

		else:
			record.nota_credito = ""

	def llamar_ebi_pac(self):
		invoice_number = '000001'
		# user_name = ''
		# user_email = ''
		monto_total = ''
		dictsItems = {}
		info_items_array = []
		lines_ids = ()
		info_pagos = []
		url_wsdl = ''
		
		for record in self:
			invoice_number = record.name
			monto_sin_impuesto = record.amount_untaxed
			grupo_monto_impuestos = record.amount_by_group
			monto_total_factura = record.amount_total
			# user_name = record.partner_id.name
			# user_email = record.partner_id.email
			lines_ids = record.invoice_line_ids

			ids_str = str(lines_ids).replace("account.move.line",
											 "").replace("(", "").replace(")", "")
			isd_array = ids_str.split(', ')

			if len(isd_array) > 1:
				tuple_ids_str = tuple(map(int, ids_str.split(', ')))
			else:
				tuple_ids_str = tuple(
					map(int, ids_str.replace(",", "").split(', ')))

			logging.info("los Ids de las lineas:" + str(lines_ids))
			# Get invoice items account.move.line
			invoice_items = self.env["account.move.line"].search(
				[('id', 'in', tuple_ids_str)])
			# set the invoice_items length
			cantidad_items = len(invoice_items)
			# Send the array of items and build the array of objects
			info_items_array = self.set_array_item_object(invoice_items)  # return array of items objects

		payments_items = self.env["account.payment"].search(
			[('communication', '=', self.name)])
		logging.info("Los pagos en v13:" + str(payments_items))

			
		tuple_impuesto_completo = grupo_monto_impuestos[0]
		monto_impuesto_completo = tuple_impuesto_completo[1]
		# get an array to info_pagos
		info_pagos = self.set_array_info_pagos(payments_items, monto_impuesto_completo)

		# constultamos el objeto de nuestra configuración del servicio
		config_document_obj = self.env["electronic.invoice"].search(
			[('name', '=', 'ebi-pac')], limit=1)
		if config_document_obj:
			fiscalN = (
				str(config_document_obj.numeroDocumentoFiscal).rjust(10, '0'))
			puntoFacturacion = (
				str(config_document_obj.puntoFacturacionFiscal).rjust(3, '0'))
			tokenEmpresa = config_document_obj.tokenEmpresa
			tokenPassword = config_document_obj.tokenPassword
			codigoSucursal = config_document_obj.codigoSucursalEmisor
			url_wsdl = config_document_obj.wsdl

		wsdl = url_wsdl
		cliente = zeep.Client(wsdl=wsdl)
		# get the client dict
		# TODO: send more parameters example: ruc, pais, razon...
		clienteDict = self.set_cliente_dict()
		# get the subtotales dict
		subTotalesDict = self.set_subtotales_dict(monto_sin_impuesto, monto_total_factura, cantidad_items, monto_impuesto_completo, info_items_array, info_pagos)
		lista_forma_pago_dict = dict(formaPago=info_pagos)
		retencion_dict = {
					'codigoRetencion': "2",
					'montoRetencion':  str('%.2f' % round((monto_total_factura - monto_sin_impuesto), 2))
				}

		totales_subtotales_inv_dict = dict(
			subTotalesDict,
			listaFormaPago=lista_forma_pago_dict
		)

		if(len(grupo_monto_impuestos) > 1):
			tuple_retencion = grupo_monto_impuestos[1]
			if(float(tuple_retencion[1]) < 0 == True):
				totales_subtotales_inv_dict["retencion"] = retencion_dict


		logging.info("Total =" + str('%.2f' % round(self.total_precio_descuento, 2)))
		descuentoBonificacion_dict = dict(
			descuentoBonificacion = {
				"descDescuento":"Descuentos aplicados a los productos",
				"montoDescuento":str('%.2f' % round(self.total_precio_descuento, 2))
			}
		)

		if(self.total_precio_descuento > 0):
			totales_subtotales_inv_dict["listaDescBonificacion"] = [descuentoBonificacion_dict]

		logging.info("Total objeto" + str(totales_subtotales_inv_dict))
		datos = dict(
			tokenEmpresa=tokenEmpresa,
			tokenPassword=tokenPassword,
			documento=dict(
				codigoSucursalEmisor=codigoSucursal,
				tipoSucursal="1",
				datosTransaccion=self.set_datosTransaccion_dict(
					fiscalN, puntoFacturacion, clienteDict),
				listaItems=dict(
					item=info_items_array
				),
				totalesSubTotales=totales_subtotales_inv_dict
			)
		)
		# datos del EBI Completos
		logging.info('DATOS DE EBI COMPLETOS: ' + str(datos))
		# send request to EBIPAC SERVICE
		logging.info('Monto Total: ' + str(self.amount_total) +
					 "Residuo: " + str(self.amount_residual))
		if (self.tipo_documento_fe != "04") or (self.tipo_documento_fe == "04" and str(self.amount_residual) != "0.0"):
			res = (cliente.service.Enviar(**datos))
			logging.info('Response code: ' + str(res.codigo))
			if(int(res['codigo']) == 200):
				self.insert_data_to_electronic_invoice_moves(
					res, invoice_number)

				tipo_doc_text = "Factura Electrónica Creada" + \
					" :<br> <b>CUFE:</b> (<a target='_blank' href='" + \
					res.qr+"'>"+str(res.cufe)+")</a><br>"
				if self.tipo_documento_fe == "04":
					tipo_doc_text = "Nota de Crédito Creada" + \
						" :<br> <b>CUFE:</b> (<a target='_blank' href='" + \
						res.qr+"'>"+str(res.cufe)+")</a><br>"

				if self.tipo_documento_fe == "09":
					tipo_doc_text = "Reembolso Creado Correctamente."

				body = tipo_doc_text
				#body = "Factura Electrónica Creada:<br> <b>CUFE:</b> (<a href='"+res.qr+"'>"+str(res.cufe)+")</a><br> <b>QR:</b><br> <img src='https://static.semrush.com/blog/uploads/media/43/b0/43b0b9a04c8a433a0c52360c9cc9aaf2/seo-guide-to-yoast-for-wordpress.svg'  height='288' width='388'/>"
				#records = self._get_followers(cr, uid, ids, None, None, context=context)
				#followers = records[ids[0]]['message_follower_ids']
				self.message_post(body=body)

				# add QR in invoice info
				self.generate_qr_in_invoice(res)
				# generate the pdf document
				self.action_download_fe_pdf(self.lastFiscalNumber)
			else:
				self.insert_data_to_logs(res, invoice_number)
				#self.insert_data_to_electronic_invoice_moves(res, invoice_number)
				body = "Factura Electrónica No Generada:<br> <b style='color:red;'>Error " + \
					res.codigo+":</b> ("+res.mensaje+")<br>"
				self.message_post(body=body)
		else:
			self.send_anulation_fe()

	def generate_qr_in_invoice(self, res):
		qr = qrcode.QRCode(
			version=1,
			error_correction=qrcode.constants.ERROR_CORRECT_L,
			box_size=10,
			border=4,
		)
		qr.add_data(res.qr)
		qr.make(fit=True)
		img = qr.make_image()
		temp = BytesIO()
		img.save(temp, format="PNG")
		qr_image = base64.b64encode(temp.getvalue())
		self.qr_code = qr_image

	def set_datosTransaccion_dict(self, fiscalN, puntoFacturacion, clienteDict):

		# output_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
		output_date = self.invoice_date.strftime("%Y-%m-%dT%H:%M:%SZ")
		fecha_fe_cn = ""
		cufe_fe_cn = ""
		invoice_fe_cn = ""
		fiscal_number_cn = ""
		last_invoice_number = ""

		logging.info("" + str(self.reversed_entry_id.id))
		original_invoice_id = self.env["account.move"].search(
			[('id', '=', self.reversed_entry_id.id)], limit=1)
		if original_invoice_id:
			last_invoice_number = original_invoice_id.name

		original_invoice_info = self.env["electronic.invoice.moves"].search(
			[('invoiceNumber', '=', last_invoice_number)], limit=1)
		if original_invoice_info:
			fecha_fe_cn = original_invoice_info.fechaRDGI
			cufe_fe_cn = original_invoice_info.cufe
			invoice_fe_cn = original_invoice_info.invoiceNumber
			fiscal_number_cn = original_invoice_info.numeroDocumentoFiscal

		logging.info("Tipo de Documento Nota Crédito: " +
					 self.tipo_documento_fe)

		informacionInteres = ""
		if self.narration:
			informacionInteres = self.narration
		# DatosFactura
		datosTransaccion = dict({
			"tipoEmision": self.tipo_emision_fe,
			"tipoDocumento": self.tipo_documento_fe,
			"numeroDocumentoFiscal": self.lastFiscalNumber,
			"puntoFacturacionFiscal": puntoFacturacion,
			"naturalezaOperacion": self.naturaleza_operacion_fe,
			"tipoOperacion": self.tipo_operacion_fe,
			"destinoOperacion": self.destino_operacion_fe,
			"formatoCAFE": self.formatoCAFE_fe,
			"entregaCAFE": self.entregaCAFE_fe,
			"envioContenedor": self.envioContenedor_fe,
			"procesoGeneracion": self.procesoGeneracion_fe,
			"tipoVenta": self.tipoVenta_fe,
			"informacionInteres": informacionInteres,
			"fechaEmision": str(output_date).replace("Z", "-05:00"),
			"cliente": clienteDict
		})

		if datosTransaccion["tipoEmision"] in ('02', '04'):

			datosTransaccion["fechaInicioContingencia"] = self.fecha_inicio_contingencia.strftime(
				"%Y-%m-%dT%I:%M:%S-05:00")
			# Minimo 15 caracteres
			datosTransaccion["motivoContingencia"] = self.motivo_contingencia

		if self.tipo_documento_fe == "04":
			datosTransaccion["listaDocsFiscalReferenciados"] = dict({
				"docFiscalReferenciado": {
					# fecha_fe_cn,
					"fechaEmisionDocFiscalReferenciado": str(output_date).replace("Z", "-05:00"),
					"cufeFEReferenciada": cufe_fe_cn,
					# "cufeFEReferenciada":'',
					# "nroFacturaPapel": fiscal_number_cn,
					# "nroFacturaImpFiscal":fiscal_number_cn
				}
			})

		logging.info('Datos de la transaccion: ' + str(datosTransaccion))
		return datosTransaccion

	def send_anulation_fe(self):
		logging.info('Llamar anulacion... ')
		context = self._context
		url_wsdl = ''
		#self.delete_file(self.env.cr, context.get('uid'))
		document = self.env["electronic.invoice"].search(
			[('name', '=', 'ebi-pac')], limit=1)

		if document:
			# (str(document.numeroDocumentoFiscal).rjust(10, '0'))
			fiscalN = self.lastFiscalNumber
			puntoFacturacion = (
				str(document.puntoFacturacionFiscal).rjust(3, '0'))
			tokenEmpresa = document.tokenEmpresa
			tokenPassword = document.tokenPassword
			codigoSucursal = document.codigoSucursalEmisor
			url_wsdl = document.wsdl

		inv_lastFiscalNumber = ""
		inv_tipo_documento_fe = ""
		inv_tipo_emision_fe = ""
		inv_name = ""

		#creditnote = self.env["account.move"].search([('reversed_entry_id','=',self.name)],limit = 1)
		# if creditnote:
		#inv_lastFiscalNumber = creditnote.lastFiscalNumber
		#inv_tipo_documento_fe = creditnote.tipo_documento_fe
		#inv_tipo_emision_fe = creditnote.tipo_emision_fe

		original_invoice_id = self.env["account.move"].search(
			[('id', '=', self.reversed_entry_id.id)], limit=1)
		if original_invoice_id:
			#payment = original_invoice_id.payment_state
			inv_lastFiscalNumber = original_invoice_id.lastFiscalNumber
			inv_tipo_documento_fe = original_invoice_id.tipo_documento_fe
			inv_tipo_emision_fe = original_invoice_id.tipo_emision_fe

		wsdl = url_wsdl
		client = zeep.Client(wsdl=wsdl)
		logging.info('Fiscal invoice number: ' + str(fiscalN))
		datos = dict(
			tokenEmpresa=tokenEmpresa,
			tokenPassword=tokenPassword,
			motivoAnulacion="Este es el motivo de anulación de la factura: " +
			self.reversal_reason_fe,  # motivo_Anulacion,
			datosDocumento=dict(
				{
					"codigoSucursalEmisor": codigoSucursal,
					"numeroDocumentoFiscal": inv_lastFiscalNumber,
					"puntoFacturacionFiscal": puntoFacturacion,
					"tipoDocumento": inv_tipo_documento_fe,
					"tipoEmision": inv_tipo_emision_fe
				}),
		)

		res = (client.service.AnulacionDocumento(**datos))
		logging.info("Objeto Enviado: " + str(datos))
		logging.info("texto de ejecución de anulacion: " + str(res))
		if(int(res['codigo']) == 200):
			original_invoice_id.state = "cancel"
			self.pagadoCompleto = "FECompletada"
			body = "Mensaje: "+res.resultado + \
				": <br> <b> ("+str(res.mensaje)+")</b><br>"
			self.message_post(body=body)
			self.action_download_fe_pdf(inv_lastFiscalNumber)
			original_invoice_id = self.env["account.move"].search(
				[('id', '=', self.reversed_entry_id.id)], limit=1)
			if original_invoice_id:
				inv_lastFiscalNumber = original_invoice_id.lastFiscalNumber
				inv_tipo_documento_fe = original_invoice_id.tipo_documento_fe
				inv_tipo_emision_fe = original_invoice_id.tipo_emision_fe
				inv_name = original_invoice_id.name
			body = "Nota de Crédito Generada: " + \
				str(self.name)+".<br> <b>Factura: </b> (" + \
				inv_name+")<br> Anulada Correctamente."
			self.message_post(body=body)

	def action_download_fe_pdf(self, FiscalNumber):
		# logging.info('Llamar a crear PDF... ')

		document = self.env["electronic.invoice"].search(
			[('name', '=', 'ebi-pac')], limit=1)

		if document:
			# self.lastFiscalNumber #(str(document.numeroDocumentoFiscal).rjust(10, '0'))
			fiscalN = FiscalNumber
			puntoFacturacion = (
				str(document.puntoFacturacionFiscal).rjust(3, '0'))
			tokenEmpresa = document.tokenEmpresa
			tokenPassword = document.tokenPassword
			codigoSucursal = document.codigoSucursalEmisor
			url_wsdl = document.wsdl
			inv_tipo_documento_fe = ""
			inv_tipo_emision_fe = ""

		if self.tipo_documento_fe == "04" and str(self.amount_residual) == "0.0":
			original_invoice_id = self.env["account.move"].search(
				[('id', '=', self.reversed_entry_id.id)], limit=1)
			if original_invoice_id:
				inv_lastFiscalNumber = original_invoice_id.lastFiscalNumber
				inv_tipo_documento_fe = original_invoice_id.tipo_documento_fe
				inv_tipo_emision_fe = original_invoice_id.tipo_emision_fe
		else:
			inv_tipo_documento_fe = self.tipo_documento_fe
			inv_tipo_emision_fe = self.tipo_emision_fe

		wsdl = url_wsdl
		docClient = zeep.Client(wsdl=wsdl)

		datosToDownloadPdf = dict(
			tokenEmpresa=tokenEmpresa,
			tokenPassword=tokenPassword,
			datosDocumento=dict(
				{
					"codigoSucursalEmisor": codigoSucursal,
					"numeroDocumentoFiscal": fiscalN,
					"puntoFacturacionFiscal": puntoFacturacion,
					"tipoDocumento": inv_tipo_documento_fe,
					"tipoEmision": inv_tipo_emision_fe
				}),
		)

		res = (docClient.service.DescargaPDF(**datosToDownloadPdf))
		logging.info('Respuesta PDF RES:' + str(res))
		logging.info('Documento EF PDF:' + str(res['documento']))
		# Define the Base64 string of the PDF file
		b64 = str(res['documento'])
		#self.insert_data_to_electronic_invoice_moves(res, self.invoice_number)
		#body = "<a href='data:application/pdf;base64,"+b64+"' target='_blank' download='HSFE.pdf'><i class='fa fa-file-pdf-o'></i>HSFE.pdf</a>"
		#body = "Factura Electrónica Creada:<br> <b>CUFE:</b> (<a href='"+res.qr+"'>"+str(res.cufe)+")</a><br> <b>QR:</b><br> <img src='https://static.semrush.com/blog/uploads/media/43/b0/43b0b9a04c8a433a0c52360c9cc9aaf2/seo-guide-to-yoast-for-wordpress.svg'  height='288' width='388'/>"
		#records = self._get_followers(cr, uid, ids, None, None, context=context)
		#followers = records[ids[0]]['message_follower_ids']
		# self.message_post(body=body)

		#pdf = self.env.ref('module_name..report_id').render_qweb_pdf(self.ids)
		b64_pdf = b64  # base64.b64encode(pdf[0])
		# save pdf as attachment
		name = self.lastFiscalNumber
		# if str(self.payment_state) == "reversed":
		#name = name + "-Anulada"

		return self.env['ir.attachment'].create({
			'name': name + str(".pdf"),
			'type': 'binary',
			'datas': b64_pdf,
			'res_model': self._name,
			'res_id': self.id,
			'mimetype': 'application/x-pdf'
		})

	def delete_file(self, cr, uid):
		#id_list = []
		cr.execute("DELETE FROM ir_attachment WHERE name = '" +
				   self.lastFiscalNumber+"'")
		cr.commit()
		logging.info("CR" + str(cr))

	def insert_data_to_electronic_invoice_moves(self, res, invoice_number):
		# Save the log info
		self.env['electronic.invoice.logs'].create({
			'codigo': res['codigo'],
			'mensaje': res['mensaje'],
			'resultado': res['resultado'],
			'invoiceNumber': invoice_number
		})

		# Save the move info
		self.env['electronic.invoice.moves'].create({
			'cufe': res['cufe'],
			'qr': res['qr'],
			'invoiceNumber': invoice_number,
			'fechaRDGI': res['fechaRecepcionDGI'],
			'numeroDocumentoFiscal':  self.lastFiscalNumber,
			'puntoFacturacionFiscal': self.puntoFactFiscal,
		})

	def insert_data_to_logs(self, res, invoice_number):

		self.env['electronic.invoice.logs'].create({
			'codigo': res['codigo'],
			'mensaje': res['mensaje'],
			'resultado': res['resultado'],
			'invoiceNumber': invoice_number
		})

	def get_taxes_in_group(self, group_children_taxes):
		items = {}
		for item in group_children_taxes:
			if "retención" in str(item.name).lower() or "retención" in str(item.name).lower():
				items['itbmRetencion'] = item.amount
			
			if "7" in str(item.name).lower() or "10" in str(item.name).lower() or "15" in str(item.name).lower():
				items['itbmPercent'] = item.amount
			# items.append(item.amount)

		return items


	def set_array_item_object(self, invoice_items):
		typeCustomers = self.partner_id.TipoClienteFE
		tasaITBMS = 'asas'
		monto_porcentaje=0.0
		array_items = []
		if invoice_items:
			for item in invoice_items:
				logging.info("Product ID:" + str(item))
				if item.tax_ids:
					tax_ids_str = str(item.tax_ids).replace("account.tax", "").replace(
						"(", "").replace(")", "").replace(",", "")
					# logging.info("Tax IDS:" + str(tuple_tax_ids_str))
					if len(tax_ids_str) > 1:
						tuple_tax_ids_str = tuple(
							map(int, tax_ids_str.split(', ')))
					else:
						tuple_tax_ids_str = tuple(
							map(int, tax_ids_str.replace(",", "").split(', ')))
					#tuple_tax_ids_str = tuple(map(int, tax_ids_str.split(', ')))
					tax_item = self.env["account.tax"].search(
						[('id', 'in', tuple_tax_ids_str)], limit=1)
				else:
					tax_item = False

				if tax_item:
					if tax_item:
						if tax_item.amount_type == 'percent':
							monto_porcentaje = tax_item.amount
							if int(tax_item.amount) == 0:
								tasaITBMS = "00"
								# logging.info("Tasa ITBMS 0= "+ str(tasaITBMS))
							if int(tax_item.amount) == 15:
								tasaITBMS = "03" 

							if int(tax_item.amount) == 10:
								tasaITBMS = "02" 
							
							if int(tax_item.amount) == 7:
								tasaITBMS = "01"
						elif tax_item.amount_type == 'group':
							# logging.info("tax_item.amount_type.children:" + str(tax_item.children_tax_ids))
							ctax_ids_str = str(tax_item.children_tax_ids).replace("account.tax","").replace("(","").replace(")","") #.replace(",","")
							# logging.info("children tuple ids str:" + str(ctax_ids_str))
							if len(ctax_ids_str)>1:
								ctuple_tax_ids_str = tuple(map(int, ctax_ids_str.split(', '))) 
							else:
								ctuple_tax_ids_str = tuple(map(int, ctax_ids_str.replace(",","").split(', ')))

							# logging.info("children tuple ids:" + str(ctuple_tax_ids_str))
							group_tax_children = self.env["account.tax"].search([('id','in',ctuple_tax_ids_str)])
							# logging.info("Children taxes:" + str(group_tax_children))
							obj_sub_impuestos = self.get_taxes_in_group(group_tax_children)
							logging.info("array subimpuestos: " + str(obj_sub_impuestos))
							monto_porcentaje = obj_sub_impuestos['itbmPercent']
							if int(obj_sub_impuestos['itbmPercent']) == 0:
								tasaITBMS = "00"
								# logging.info("Tasa ITBMS 0= "+ str(tasaITBMS))
							if int(obj_sub_impuestos['itbmPercent']) == 15:
								tasaITBMS = "03" 

							if int(obj_sub_impuestos['itbmPercent']) == 10:
								tasaITBMS = "02" 
							
							if int(obj_sub_impuestos['itbmPercent']) == 7:
								tasaITBMS = "01"
				else:
					tasaITBMS = "00"
					monto_porcentaje = 0

				
				precioDescuento = '0'
				if item.discount > 0:
					precioDescuento = str((float(item.price_unit) * float(item.discount)) / 100)

				logging.info("Descuento:"+ str(precioDescuento))
				self.total_precio_descuento += float(precioDescuento)

				new_item_object = {}
				new_item_object['descripcion'] = str(item.name)
				new_item_object['cantidad'] = str(
					'%.2f' % round(item.quantity, 2))
				new_item_object['precioUnitario'] = str('%.2f' % round(item.price_unit, 2))
				new_item_object['precioUnitarioDescuento'] = str('%.2f' % round(float(precioDescuento),2))
				new_item_object['precioItem'] = str('%.2f' % round((item.quantity * (item.price_unit - float(precioDescuento))), 2))
				new_item_object['valorTotal'] = str('%.2f' % round((((item.quantity * (item.price_unit - float(precioDescuento))) + ((item.price_subtotal * monto_porcentaje)/100))), 2))
				new_item_object['codigoGTIN'] = str("")
				new_item_object['cantGTINCom'] = str("")
				new_item_object['codigoGTINInv'] = str(item.product_id.codigoGTINInv) if item.product_id.codigoGTINInv else ''
				new_item_object['tasaITBMS'] = str(tasaITBMS)
				new_item_object['valorITBMS'] = str('%.2f' % round((item.price_subtotal * monto_porcentaje)/100, 2))
				new_item_object['cantGTINComInv'] = str("")
	
				if item.product_id.categoryProduct == 'Materia prima Farmacéutica' or item.product_id.categoryProduct == 'Medicina' or item.product_id.categoryProduct == 'Alimento':
					new_item_object['fechaFabricacion'] = str(
						item.fechaFabricacion.strftime("%Y-%m-%dT%I:%M:%S-05:00"))
					new_item_object['fechaCaducidad'] = str(
						item.fechaCaducidad.strftime("%Y-%m-%dT%I:%M:%S-05:00"))

				# if typeCustomers=="03":
				# 	new_item_object["CodigoCPBS"]=item.product_id.codigoCPBS

				# if item.tasaISC:
				# 	new_item_object["TasaISC"]=item.product_id.codigoCPBS

				# if item.valorISC:
				# 	new_item_object["ValorISC"]=item.product_id.valorISC

				# if item.tasaOTI:
				# 	new_item_object["tasaOTI"]=item.product_id.tasaOTI

				# if item.valorTasa:
				# 	new_item_object["valorTasa"]=item.product_id.valorTasa

				array_items.append(new_item_object)
		logging.info("Product info" + str(array_items))
		return array_items

	def set_array_info_pagos(self, payments_items, monto_impuesto_completo):
		array_pagos = []
		if payments_items:
			for item in payments_items:
				payment_item_obj = {}
				payment_item_obj['formaPagoFact'] = "02"
				payment_item_obj['descFormaPago'] = ""
				payment_item_obj['valorCuotaPagada'] = str(
					'%.2f' % round(item.amount, 2))
				array_pagos.append(payment_item_obj)
		else:
			nuevo_diccionario2 = {}
			nuevo_diccionario2['formaPagoFact'] = "01"
			nuevo_diccionario2['descFormaPago'] = ""
			nuevo_diccionario2['valorCuotaPagada'] = str(
				'%.2f' % round(float((self.amount_untaxed + monto_impuesto_completo)-self.total_precio_descuento), 2))
			array_pagos.append(nuevo_diccionario2)

		logging.info('Montos de Pagos: ' + str(array_pagos))
		return array_pagos


	def set_cliente_dict(self):

		tipo_cliente_fe = self.partner_id.TipoClienteFE #'02'
		tipo_contribuyente = self.partner_id.tipoContribuyente #Juridico
		client_obj = {
			"tipoClienteFE" : tipo_cliente_fe, #reemplazar por TipoclienteFE desde res.partner
			"tipoContribuyente": tipo_contribuyente,
			"numeroRUC" : self.partner_id.numeroRUC,
			"pais": self.partner_id.country_id.code,
			"correoElectronico1" : self.partner_id.email,
			# "razonSocial" : user_name
		}
		# check if TipoClienteFE is 01/03
		if tipo_cliente_fe in ('01', '03'):
			client_obj['digitoVerificadorRUC'] = self.partner_id.digitoVerificadorRUC #viene de res.partner
			client_obj['razonSocial']          = self.partner_id.razonSocial #'test razón social'
			client_obj['direccion']            = self.partner_id.direccion #'Urbanización, Calle, Casa, Número de Local'
			client_obj['codigoUbicacion']      = self.partner_id.CodigoUbicacion #'8-8-8'
			client_obj['provincia']            = self.partner_id.provincia #'8'
			client_obj['distrito']             = self.partner_id.distrito #'8'
			client_obj['corregimiento']        = self.partner_id.corregimiento #'8'

		if tipo_cliente_fe in ('04'):
			tipoIdentificacion =  self.partner_id.tipoIdentificacion#'01'
			client_obj['tipoIdentificacion'] = tipoIdentificacion#'01'
			client_obj['nroIdentificacionExtranjero'] = self.partner_id.nroIdentificacionExtranjero#'Número de Pasaporte o Número de Identificación Tributaria Extranjera' 
			if tipoIdentificacion == '01':
				client_obj['paisExtranjero'] = self.partner_id.paisExtranjero#'Utilizar nombre completo del país.'

		return client_obj


	def set_subtotales_dict(self, monto_sin_impuesto, monto_total_factura, cantidad_items,monto_impuesto_completo, info_items_array, info_pagos):
		# logging.info("Array items: " + str(info_items_array))

		total_todos_items = 0.0
		for item in info_items_array:
			total_todos_items += float(item['valorTotal'])


		subTotalesDict = {}
		subTotalesDict['totalPrecioNeto'] = str('%.2f' % round(monto_sin_impuesto, 2))
		subTotalesDict['totalITBMS'] = str('%.2f' % round(monto_impuesto_completo, 2)) #str('%.2f' % round((monto_total_factura - monto_sin_impuesto), 2))
		# subTotalesDict['totalISC'] = #Suma de todas las ocurrencias de ValorISC.
		subTotalesDict['totalMontoGravado'] = str('%.2f' % round(monto_impuesto_completo, 2)) #sumar TotalISC
		subTotalesDict['totalDescuento'] = ""
		subTotalesDict['totalAcarreoCobrado'] = ""
		subTotalesDict['valorSeguroCobrado'] = ""
		subTotalesDict['totalFactura'] =str('%.2f' % round(((monto_sin_impuesto + monto_impuesto_completo) - self.total_precio_descuento), 2))  #str('%.2f' % round(monto_total_factura, 2))
		subTotalesDict['totalValorRecibido'] = str('%.2f' % round(((monto_sin_impuesto + monto_impuesto_completo) - self.total_precio_descuento), 2)) #str('%.2f' % round(monto_total_factura, 2))
		subTotalesDict['vuelto'] = "0.00"
		subTotalesDict['tiempoPago'] = "1"
		subTotalesDict['nroItems'] = str(cantidad_items)
		subTotalesDict['totalTodosItems'] = str('%.2f' % round(total_todos_items, 2)) #str('%.2f' % round(monto_total_factura, 2))

		if(self.total_precio_descuento > 0):
			subTotalesDict['totalDescuento'] = str('%.2f' % round(self.total_precio_descuento, 2))
		
		return subTotalesDict
