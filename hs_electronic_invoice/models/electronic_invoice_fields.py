# -*- coding: utf-8 -*-

import base64
from cmath import log
from io import BytesIO
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
	lastFiscalNumber = fields.Char(string="Número Fiscal", compute="on_change_state", readonly = "True", store="True")
	puntoFactFiscal = fields.Char(string="Punto Facturación Fiscal", readonly = "True")
	pagadoCompleto = fields.Char(string="Estado de Pago", compute="on_change_pago", readonly = "True", store="True")
	qr_code = fields.Binary("QR Factura Electrónica", attachment=True, readonly = "True")
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
	fecha_inicio_contingencia = fields.Date(string = 'Fecha Inicio de Contingencia')
	motivo_contingencia = fields.Char(string = 'Motivo de Contingencia')
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
	reversal_reason_fe = fields.Char(string = 'Reason', readonly = "True")
	reembolso = fields.Char(string = 'Reembolso', compute="on_change_payment_state", readonly = "True")
	anulado =  fields.Char(string = 'Anulado', readonly = "True", store="True")
	nota_credito =  fields.Char(string = 'Nota de Crédito', readonly = "True", compute="on_change_move_type",)

	@api.depends('qr_code')
	def on_change_pago(self):
		for record in self:
				# logging.info('Blank QR: ' + str(record.qr_code))
				#if str(record.amount_residual) == '0.0' and record.lastFiscalNumber:
				if str(record.qr_code) != "False":
					record.pagadoCompleto = 'FECompletada'
					#self.llamar_ebi_pac()
					#logging.info('Amoount Valor: ' + str(record.amount_residual))
				else:
					record.pagadoCompleto = 'Pendiente'

	@api.depends('state')
	def on_change_state(self):
		logging.info('Entró al onchange: ')
		for record in self:
			logging.info('HSInvoice: ' + str(record.amount_residual) + ":" + str( record.lastFiscalNumber))
			if record.state == 'posted' and record.pagadoCompleto != "NumeroAsignado":
				record.pagadoCompleto = "NumeroAsignado"
				if record.lastFiscalNumber == False:				
					#record.lastFiscalNumber = '000045'
					#first_id = self.env['electronic.invoice'].search([('payment_id','=',rec.invoice_payment_term_id.id)], order='days asc')[0].id
					document = self.env["electronic.invoice"].search([('name','=','ebi-pac')],limit = 1)
					if document:
						fiscalN = (str(document.numeroDocumentoFiscal).rjust(10, '0'))
						puntoFacturacion  = (str(document.puntoFacturacionFiscal).rjust(3, '0'))

						record.lastFiscalNumber = fiscalN
						record.puntoFactFiscal = puntoFacturacion
					
						document.numeroDocumentoFiscal = str(int(document.numeroDocumentoFiscal)+1)

	@api.depends('move_type', 'partner_id')
	def on_change_move_type(self):
		logging.info("El Movimiento es:"+ str(self.move_type))
		logging.info("Reversed Entry: " + str(self.reversed_entry_id.id))
		if  self.move_type != False:
			logging.info("ENTRO AL IFFF:"+ str(self.move_type))
			logging.info("Payment State Valor:" + str(self.payment_state))
			for record in self:
				if  record.move_type == 'out_refund' and record.payment_state == "paid":
					logging.info('Entró a Nota de Crédito: NCRFE - Anulación')
					record.tipo_documento_fe = "04"
					record.nota_credito ="NotaCredito"
				else:
					record.nota_credito =""
					if record.move_type == 'out_refund' and record.state == "draft" and record.reversed_entry_id.id != False: #and self.payment_state == "not_paid":
						
						original_invoice_id = self.env["account.move"].search([('id','=',self.reversed_entry_id.id)],limit = 1)
						if original_invoice_id:
							payment = original_invoice_id.payment_state
							if payment != "not_paid" and payment != "reversed" :
								logging.info('Entró a Nota de Crédito: Reembolso')
								record.tipo_documento_fe = "09"
								record.nota_credito ="Reembolso"
							else:
								logging.info('Entró a Nota de Crédito: NCRFE PARCIAL.')
								self.tipo_documento_fe = "04"
								self.nota_credito ="NotaCredito"
					else:
						if record.move_type == 'out_refund' and record.state == "draft" and record.reversed_entry_id.id == False: #and self.payment_state == "not_paid":
							logging.info('Entró a Nota de Crédito: NCG')
							record.tipo_documento_fe = "06"
							record.nota_credito ="NotaCredito"

		else:
					record.nota_credito =""

	@api.depends('payment_state')
	def on_change_payment_state(self):
		for record in self:
			if str(record.payment_state) == "reversed":
				if(record.anulado != 'Anulado'):	
					#self.send_anulation_fe()
					record.anulado = "Anulado"
					record.reembolso = 'Reembolso'
				else:
					record.reembolso = 'Anulado'
			else:
				record.reembolso = ''
						
	def llamar_ebi_pac(self):
		invoice_number = '000001'
		user_name = ''
		user_email = ''
		monto_total = ''
		dictsItems = {}
		info_items_array = []
		lines_ids = ()
		info_pagos = []

		for record in self:
			invoice_number = record.name
			monto_sin_impuesto = record.amount_untaxed
			monto_impuestos = record.amount_by_group
			monto_total_factura = record.amount_total
			user_name = record.partner_id.name
			user_email= record.partner_id.email
			lines_ids = record.invoice_line_ids 

			ids_str = str(lines_ids).replace("account.move.line","").replace("(","").replace(")","")
			isd_array = ids_str.split(', ')

			if len(isd_array)>1:
				tuple_ids_str =tuple(map(int, ids_str.split(', ')))
			else:
				tuple_ids_str =tuple(map(int, ids_str.replace(",","").split(', ')))

			logging.info("los Ids de las lineas:" + str(lines_ids))
			# Get invoice items account.move.line
			invoice_items = self.env["account.move.line"].search([('id','in',tuple_ids_str)])
			# set the invoice_items length
			cantidad_items = len(invoice_items)
			# Send the array of items and build the array of objects
			info_items_array = self.set_array_item_object(invoice_items) #return array of items objects		

		payments_items = self.env["account.payment"].search([('ref','=',str(invoice_number))])
		#get an array to info_pagos
		info_pagos = self.set_array_info_pagos(payments_items)
		
		# constultamos el objeto de nuestra configuración del servicio
		config_document_obj = self.env["electronic.invoice"].search([('name','=','ebi-pac')],limit = 1)
		if config_document_obj:
			fiscalN = (str(config_document_obj.numeroDocumentoFiscal).rjust(10, '0'))
			puntoFacturacion  = (str(config_document_obj.puntoFacturacionFiscal).rjust(3, '0'))
			tokenEmpresa = config_document_obj.tokenEmpresa
			tokenPassword = config_document_obj.tokenPassword
			codigoSucursal = config_document_obj.codigoSucursalEmisor
			url_wsdl = config_document_obj.wsdl
		
		wsdl = url_wsdl
		cliente = zeep.Client(wsdl=wsdl)
		# get the client dict
		clienteDict = self.set_cliente_dict(user_name, user_email) #TODO: send more parameters example: ruc, pais, razon...
		# get the subtotales dict
		subTotalesDict = self.set_subtotales_dict(monto_sin_impuesto, monto_total_factura, cantidad_items)

		datos = dict(
			tokenEmpresa=tokenEmpresa,
			tokenPassword=tokenPassword,
			documento=dict(
				codigoSucursalEmisor=codigoSucursal,
				tipoSucursal="1",
				datosTransaccion=self.set_datosTransaccion_dict(fiscalN, puntoFacturacion, clienteDict),
				listaItems=dict(
					item=info_items_array
				),
				totalesSubTotales=dict(subTotalesDict,
					listaFormaPago= dict(
						formaPago = info_pagos
					)
				)
			)
		)	
		#datos del EBI Completos
		logging.info('DATOS DE EBI COMPLETOS: ' + str(datos))
		# send request to EBIPAC SERVICE
		if (self.tipo_documento_fe != "04") or (self.tipo_documento_fe == "04" and self.payment_state != "paid"):
			res = (cliente.service.Enviar(**datos))
			logging.info('Response code: ' + str(res.codigo))
			if(int(res['codigo']) == 200):
				self.insert_data_to_electronic_invoice_moves(res, invoice_number)

				tipo_doc_text = "Factura Electrónica Creada"  + " :<br> <b>CUFE:</b> (<a target='_blank' href='"+res.qr+"'>"+str(res.cufe)+")</a><br>"
				if  self.tipo_documento_fe == "04":
					tipo_doc_text ="Nota de Crédito Creada"  + " :<br> <b>CUFE:</b> (<a target='_blank' href='"+res.qr+"'>"+str(res.cufe)+")</a><br>"
				
				if  self.tipo_documento_fe == "09":
					tipo_doc_text ="Reembolso Creado Correctamente."

					


				body = tipo_doc_text
				#body = "Factura Electrónica Creada:<br> <b>CUFE:</b> (<a href='"+res.qr+"'>"+str(res.cufe)+")</a><br> <b>QR:</b><br> <img src='https://static.semrush.com/blog/uploads/media/43/b0/43b0b9a04c8a433a0c52360c9cc9aaf2/seo-guide-to-yoast-for-wordpress.svg'  height='288' width='388'/>" 
				#records = self._get_followers(cr, uid, ids, None, None, context=context)
				#followers = records[ids[0]]['message_follower_ids']
				self.message_post(body=body)
				
				#add QR in invoice info
				self.generate_qr_in_invoice(res)
				#generate the pdf document
				self.action_download_fe_pdf(self.lastFiscalNumber)
			else:
				self.insert_data_to_logs(res, invoice_number)
				#self.insert_data_to_electronic_invoice_moves(res, invoice_number)
				body = "Factura Electrónica No Generada:<br> <b style='color:red;'>Error "+res.codigo+":</b> ("+res.mensaje+")<br>"
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
		cufe_fe_cn =  ""
		invoice_fe_cn = ""
		fiscal_number_cn = ""
		last_invoice_number =""

		# logging.info("" + str(self.reversed_entry_id.id))
		original_invoice_id = self.env["account.move"].search([('id','=',self.reversed_entry_id.id)],limit = 1)
		if original_invoice_id:
			last_invoice_number = original_invoice_id.name

		original_invoice_info = self.env["electronic.invoice.moves"].search([('invoiceNumber','=',last_invoice_number)],limit = 1)
		if original_invoice_info:
			fecha_fe_cn = original_invoice_info.fechaRDGI
			cufe_fe_cn = original_invoice_info.cufe
			invoice_fe_cn = original_invoice_info.invoiceNumber
			fiscal_number_cn = original_invoice_info.numeroDocumentoFiscal

		logging.info("Tipo de Documento: " + self.tipo_documento_fe)
		# DatosFactura
		informacion_interes = "Factura interna"
		if self.tipo_documento_fe  == "09":
			informacion_interes = "Factura Reembolso"

		if self.tipo_documento_fe  == "04":
			informacion_interes = "Nota de Crédito Referente a Una o Varias FE"

		if self.tipo_documento_fe  == "06":
			informacion_interes = "Nota de Crédito Genérica"



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
			"informacionInteres": informacion_interes,
			"fechaEmision": str(output_date).replace("Z","-05:00"),
			"cliente": clienteDict
		})
		
		if datosTransaccion["tipoEmision"] in ('02', '04'):
			#Todo: Esto no me sta funcionando
			datosTransaccion["fechaInicioContingencia"] = self.fecha_inicio_contingencia.strftime("%Y-%m-%dT%I:%M:%S-05:00")
			# datosTransaccion["fechaInicioContingencia"] = '2022-03-30T04:57:00 %p'
			datosTransaccion["motivoContingencia"] = self.motivo_contingencia
		
		if self.tipo_documento_fe == "04":
			datosTransaccion["listaDocsFiscalReferenciados"] =dict({
				"docFiscalReferenciado": {
					"fechaEmisionDocFiscalReferenciado": str(output_date).replace("Z","-05:00"),#fecha_fe_cn,
					"cufeFEReferenciada":cufe_fe_cn,
					# "cufeFEReferenciada":'',
					#"nroFacturaPapel":fiscal_number_cn,
					# "nroFacturaImpFiscal":fiscal_number_cn
				}
			})

		logging.info('Datos de la transaccion: ' + str(datosTransaccion))
		return datosTransaccion

	def send_anulation_fe(self):
		logging.info('Llamar anulacion... ')
		context = self._context
		#self.delete_file(self.env.cr, context.get('uid'))
		document = self.env["electronic.invoice"].search([('name','=','ebi-pac')],limit = 1)
		
		if document:
			fiscalN = self.lastFiscalNumber #(str(document.numeroDocumentoFiscal).rjust(10, '0'))
			puntoFacturacion  = (str(document.puntoFacturacionFiscal).rjust(3, '0'))
			tokenEmpresa = document.tokenEmpresa
			tokenPassword = document.tokenPassword
			codigoSucursal = document.codigoSucursalEmisor
			url_wsdl = document.wsdl
		
		inv_lastFiscalNumber = ""
		inv_tipo_documento_fe = ""
		inv_tipo_emision_fe = ""
		inv_name = ""
		
		#creditnote = self.env["account.move"].search([('reversed_entry_id','=',self.name)],limit = 1)
		#if creditnote:
			#inv_lastFiscalNumber = creditnote.lastFiscalNumber
			#inv_tipo_documento_fe = creditnote.tipo_documento_fe
			#inv_tipo_emision_fe = creditnote.tipo_emision_fe

		original_invoice_id = self.env["account.move"].search([('id','=',self.reversed_entry_id.id)],limit = 1)
		if original_invoice_id:
			payment = original_invoice_id.payment_state
			inv_lastFiscalNumber = original_invoice_id.lastFiscalNumber
			inv_tipo_documento_fe = original_invoice_id.tipo_documento_fe
			inv_tipo_emision_fe = original_invoice_id.tipo_emision_fe

		wsdl = url_wsdl
		client = zeep.Client(wsdl=wsdl)
		logging.info('Fiscal invoice number: ' + str(fiscalN))
		datos = dict( 
		tokenEmpresa=tokenEmpresa,
		tokenPassword=tokenPassword,
		motivoAnulacion="Este es el motivo de anulación de la factura: " + self.reversal_reason_fe, #motivo_Anulacion,
		datosDocumento=dict( 
		{ 
		"codigoSucursalEmisor": codigoSucursal,
		"numeroDocumentoFiscal": inv_lastFiscalNumber,
		"puntoFacturacionFiscal": puntoFacturacion,
		"tipoDocumento": inv_tipo_documento_fe,
		"tipoEmision": inv_tipo_emision_fe
		} ),
		) 
	
		res = (client.service.AnulacionDocumento(**datos))
		logging.info("Objeto Enviado: "+  str(datos))
		logging.info("texto de ejecución de anulacion: " + str(res))
		if(int(res['codigo']) == 200):
			self.pagadoCompleto = "FECompletada"
			body = "Mensaje: "+res.resultado+": <br> <b> ("+str(res.mensaje)+")</b><br>"
			self.message_post(body=body)
			self.action_download_fe_pdf(inv_lastFiscalNumber)		
			original_invoice_id = self.env["account.move"].search([('id','=',self.reversed_entry_id.id)],limit = 1)
			if original_invoice_id:
				inv_lastFiscalNumber = original_invoice_id.lastFiscalNumber
				inv_tipo_documento_fe = original_invoice_id.tipo_documento_fe
				inv_tipo_emision_fe = original_invoice_id.tipo_emision_fe
				inv_name = original_invoice_id.name
			body = "Nota de Crédito Generada: "+str(self.name)+".<br> <b>Factura: </b> ("+inv_name+")<br> Anulada Correctamente."
			self.message_post(body=body)

	def action_download_fe_pdf(self, FiscalNumber):
		# logging.info('Llamar a crear PDF... ')

		document = self.env["electronic.invoice"].search([('name','=','ebi-pac')],limit = 1)
	
		if document:
			fiscalN = FiscalNumber#self.lastFiscalNumber #(str(document.numeroDocumentoFiscal).rjust(10, '0'))
			puntoFacturacion  = (str(document.puntoFacturacionFiscal).rjust(3, '0'))
			tokenEmpresa = document.tokenEmpresa
			tokenPassword = document.tokenPassword
			codigoSucursal = document.codigoSucursalEmisor
			url_wsdl = document.wsdl
			inv_tipo_documento_fe = ""
			inv_tipo_emision_fe = ""
		
		if  self.tipo_documento_fe == "04" and self.payment_state == "paid":
			original_invoice_id = self.env["account.move"].search([('id','=',self.reversed_entry_id.id)],limit = 1)
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
				} ),
		)
	
		res = (docClient.service.DescargaPDF(**datosToDownloadPdf))
		# logging.info('Respuesta PDF RES:' + str(res))
		# logging.info('Documento EF PDF:' + str(res['documento']))
		# Define the Base64 string of the PDF file
		b64 = str(res['documento'])
		
		b64_pdf = b64#base64.b64encode(pdf[0])
		# save pdf as attachment
		name = self.lastFiscalNumber
		if str(self.payment_state) == "reversed":
			name = name + "-Anulada"

		return self.env['ir.attachment'].create({
			'name': name,
			'type': 'binary',
			'datas': b64_pdf,
			'res_model': self._name,
			'res_id': self.id,
			'mimetype': 'application/x-pdf'
		})
	
	def delete_file(self, cr, uid):
		#id_list = []
		cr.execute("DELETE FROM ir_attachment WHERE name = '"+self.lastFiscalNumber+"'")
		cr.commit()
		logging.info("CR" + str(cr))

	def insert_data_to_electronic_invoice_moves(self, res, invoice_number):
		# Save the log info
		self.env['electronic.invoice.logs'].create({
				'codigo': res['codigo'],
				'mensaje': res['mensaje'],
				'resultado': res['resultado'],
				'invoiceNumber':invoice_number 
			})
		
		# Save the move info
		self.env['electronic.invoice.moves'].create({
				'cufe': res['cufe'],
				'qr': res['qr'],
				'invoiceNumber':invoice_number,
				'fechaRDGI': res['fechaRecepcionDGI'],
				'numeroDocumentoFiscal' :  self.lastFiscalNumber,
				'puntoFacturacionFiscal': self.puntoFactFiscal,
			})
		
	def insert_data_to_logs(self, res, invoice_number):
		
		self.env['electronic.invoice.logs'].create({
				'codigo': res['codigo'],
				'mensaje': res['mensaje'],
				'resultado': res['resultado'],
				'invoiceNumber':invoice_number
			})

	# Build item Object for item list
	def set_array_item_object(self, invoice_items):
		logging.info("Producto:" + str(invoice_items))
		array_items = []
		if invoice_items:
				for item in invoice_items:	
					#logging.info("Product ID:" + str(item) + str(item.product_id.name))	
					# logging.info("Account Tax IDS:" + str(item.tax_ids))
					# tax_ids = item.tax_ids	
					# logging.info("Account Tax IDS:" + str(tax_ids))
					if item.tax_ids:
						tax_ids_str = str(item.tax_ids).replace("account.tax","").replace("(","").replace(")","").replace(",","")
						# logging.info("Tax IDS:" + str(tuple_tax_ids_str))
						if len(tax_ids_str)>1:
							tuple_tax_ids_str =tuple(map(int, tax_ids_str.split(', ')))
						else:
							tuple_tax_ids_str =tuple(map(int, tax_ids_str.replace(",","").split(', ')))
						#tuple_tax_ids_str = tuple(map(int, tax_ids_str.split(', ')))
						tax_item = self.env["account.tax"].search([('id','in',tuple_tax_ids_str)],limit = 1)
					else:
						tax_item = False
					
					if tax_item:
						#logging.info("Tax Name:" + str(tax_item.name))
						#logging.info("Tax Name:" + str(tax_item.amount))
						monto_porcentaje = tax_item.amount
						if int(tax_item.amount) == 15:
							tasaITBMS = "03" 

						if int(tax_item.amount) == 10:
							tasaITBMS = "02" 
						
						if int(tax_item.amount) == 7:
							tasaITBMS = "01"
					else:
						tasaITBMS = "00"
						monto_porcentaje = 0
					
					new_item_object = {}
					new_item_object['descripcion'] = str(item.product_id.name)
					new_item_object['cantidad'] = str('%.2f' % round(item.quantity, 2))
					new_item_object['precioUnitario'] = str('%.2f' % round(item.price_unit, 2))
					new_item_object['precioItem'] = str('%.2f' % round((item.quantity * item.price_unit), 2))
					new_item_object['valorTotal'] = str('%.2f' % round((((item.quantity * item.price_unit) + ((item.price_unit * monto_porcentaje)/100)) - item.discount), 2))
					new_item_object['codigoGTIN'] = str("")
					new_item_object['cantGTINCom'] = str("")
					new_item_object['codigoGTINInv'] = str("")
					new_item_object['tasaITBMS'] = str(tasaITBMS)
					new_item_object['valorITBMS'] = str('%.2f' % round((item.price_unit * monto_porcentaje)/100, 2))
					new_item_object['cantGTINComInv'] = str("")

					array_items.append(new_item_object)

		return array_items

	def set_array_info_pagos(self, payments_items):
		array_pagos = []
		if payments_items:
			for item in payments_items:
					payment_item_obj = {}
					payment_item_obj['formaPagoFact'] = "02"
					payment_item_obj['descFormaPago'] = ""
					payment_item_obj['valorCuotaPagada'] = str('%.2f' % round(item.amount, 2))
					array_pagos.append(payment_item_obj)
		else:
			nuevo_diccionario2 = {}
			nuevo_diccionario2['formaPagoFact'] = "01"
			nuevo_diccionario2['descFormaPago'] = ""
			nuevo_diccionario2['valorCuotaPagada'] = str('%.2f' % round(float(self.amount_total), 2))
			array_pagos.append(nuevo_diccionario2)

		return array_pagos

	def set_cliente_dict(self, user_name, user_email):
		logging.info('Pais del cliente: ' + str(self.partner_id.country_id.code))

		client_obj = {
			"tipoClienteFE" : "02", #reemplazar por TipoclienteFE desde res.partner
			"tipoContribuyente": 1,
			"numeroRUC" : "8792965",
			"pais": str(self.partner_id.country_id.code),
			"correoElectronico1" : user_email,
			"razonSocial" : user_name
		}
		return client_obj

	def set_subtotales_dict(self, monto_sin_impuesto, monto_total_factura, cantidad_items):
			subTotalesDict = {}
			subTotalesDict['totalPrecioNeto'] = str('%.2f' % round(monto_sin_impuesto, 2))
			subTotalesDict['totalITBMS'] = str('%.2f' % round((monto_total_factura - monto_sin_impuesto), 2))
			subTotalesDict['totalMontoGravado'] = str('%.2f' % round((monto_total_factura - monto_sin_impuesto), 2))
			subTotalesDict['totalDescuento'] = ""
			subTotalesDict['totalAcarreoCobrado'] = ""
			subTotalesDict['valorSeguroCobrado'] = ""
			subTotalesDict['totalFactura'] = str('%.2f' % round(monto_total_factura, 2))
			subTotalesDict['totalValorRecibido'] = str('%.2f' % round(monto_total_factura, 2))
			subTotalesDict['vuelto'] = "0.00"
			subTotalesDict['tiempoPago'] = "1"
			subTotalesDict['nroItems'] = str(cantidad_items)
			subTotalesDict['totalTodosItems'] = str('%.2f' % round(monto_total_factura, 2))
			return subTotalesDict
