from fastapi import FastAPI, Request, Form, File, UploadFile, Query, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId
from datetime import datetime
import logging
import json
import os
import base64
import zlib
import traceback
import io
from io import BytesIO
import uuid
from PIL import Image
import subprocess
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from typing import Optional, Dict, Any, List
import sys
import shutil
import qrcode
from unidecode import unidecode
import PyPDF2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate
from reportlab.lib.units import inch
import re
import pypandoc
import asyncio
import fitz
from fastapi.responses import JSONResponse
from fastapi import HTTPException, Form, UploadFile, File
from pydantic import BaseModel
from typing import Dict, Any
import json
from reportlab.lib.utils import ImageReader
import tempfile
from dotenv import load_dotenv
# PDF related imports
# Carregar variáveis de ambiente
load_dotenv()

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar diretórios estáticos e templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configurações
MONGODB_URL = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "documentacao_ti")

# MongoDB setup
client = None
db = None

# Configurações de diretórios
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
TERMOS_FOLDER = os.path.join(BASE_DIR, "termos")
TERMOS_ASSINADOS_FOLDER = os.path.join(BASE_DIR, "termos_assinados")

# Criar pasta de uploads se não existir
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Criar pastas para termos e termos assinados
os.makedirs(TERMOS_FOLDER, exist_ok=True)
os.makedirs(TERMOS_ASSINADOS_FOLDER, exist_ok=True)

# Função para conectar ao MongoDB
async def get_database():
    try:
        client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        logger.info("Conexão com MongoDB estabelecida com sucesso")
        db = client[DATABASE_NAME]
        return db
    except Exception as e:
        logger.error(f"Erro ao conectar com MongoDB: {str(e)}\n{traceback.format_exc()}")
        return None

# Função auxiliar para converter ObjectId para string
def convert_mongo_doc(doc):
    if isinstance(doc, dict):
        return {k: convert_mongo_doc(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [convert_mongo_doc(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    else:
        return doc

# Função para gerar QR Code
def gerar_qr_code(data, output_file):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_file)
    return output_file

# Evento de inicialização
@app.on_event("startup")
async def startup_event():
    try:
        logger.info("=== Iniciando Aplicação ===")
        db = await get_database()
        
        # Criar índices e coleções necessárias
        colecoes = await db.list_collection_names()
        
        # Coleção de modelos
        if "modelos" not in colecoes:
            await db.create_collection("modelos")
            await db.modelos.create_index("nome", unique=True)
            logger.info("Coleção 'modelos' criada com sucesso!")
        
        # Coleção de termos
        if "termos" not in colecoes:
            await db.create_collection("termos")
            await db.termos.create_index("token", unique=True)
            logger.info("Coleção 'termos' criada com sucesso!")
            
        logger.info("Banco de dados inicializado com sucesso!")
        
        routes = [
            {"path": route.path, "name": route.name, "methods": route.methods}
            for route in app.routes
            if hasattr(route, 'methods')
        ]
        logger.debug(f"Rotas disponíveis: {routes}")
    except Exception as e:
        logger.error(f"Erro na inicialização: {str(e)}\n{traceback.format_exc()}")
        raise

# Rotas principais
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/cadastrar-documento", response_class=HTMLResponse)
async def pagina_cadastrar_documento(request: Request):
    return templates.TemplateResponse("cadastrar_documento.html", {"request": request})

@app.get("/cadastrar-modelo", response_class=HTMLResponse)
async def pagina_cadastrar_modelo(request: Request):
    return templates.TemplateResponse("cadastrar_documento.html", {"request": request})

@app.get("/novo-termo")
async def novo_termo(request: Request):
    return templates.TemplateResponse("novo_termo.html", {"request": request})

@app.get("/assinar-termo/{termo_id}")
async def assinar_termo(request: Request, termo_id: str):
    try:
        logger.info(f"Acessando página de assinatura para termo: {termo_id}")
        
        # Buscar termo no banco
        db = await get_database()
        termo = await db.termos.find_one({"_id": ObjectId(termo_id)})
        
        if not termo:
            raise HTTPException(status_code=404, detail="Termo não encontrado")
            
        # Converter o termo para um formato serializável
        termo = convert_mongo_doc(termo)
            
        return templates.TemplateResponse(
            "assinar_termo.html",
            {
                "request": request,
                "termo": termo,
                "ja_assinado": termo.get('status') == 'Assinado'
            }
        )
    except Exception as e:
        logger.error(f"Erro ao acessar página de assinatura: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cadastrar-modelo")
async def cadastrar_modelo(
    nome_modelo: str = Form(...),
    titulo_documento: str = Form(...),
    tipo_termo: str = Form(...),
    arquivo_rtf: UploadFile = File(...)
):
    try:
        logger.debug(f"Recebendo arquivo RTF: {arquivo_rtf.filename}")
        
        # Ler o conteúdo do arquivo em chunks para arquivos grandes
        MAX_SIZE = 50 * 1024 * 1024  # 50MB
        CHUNK_SIZE = 1024 * 1024  # 1MB
        
        conteudo = bytearray()
        tamanho_total = 0
        
        while True:
            chunk = await arquivo_rtf.read(CHUNK_SIZE)
            if not chunk:
                break
            tamanho_total += len(chunk)
            if tamanho_total > MAX_SIZE:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"Arquivo muito grande. Limite de {MAX_SIZE/(1024*1024)}MB."}
                )
            conteudo.extend(chunk)
        
        conteudo = bytes(conteudo)
        logger.debug(f"Arquivo lido. Tamanho: {tamanho_total/1024:.2f}KB")
        
        # Verificar se o arquivo começa com a assinatura RTF
        if not conteudo.startswith(b'{\\rtf'):
            # Se não for um RTF válido, tentar converter o texto para RTF
            try:
                texto = conteudo.decode('utf-8')
                # Criar cabeçalho RTF básico
                rtf_header = "{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1046"
                rtf_header += "{\\fonttbl{\\f0\\fswiss\\fcharset0 Arial;}}"
                rtf_header += "{\\colortbl ;\\red0\\green0\\blue0;}"
                rtf_header += "\\viewkind4\\uc1\\pard\\f0\\fs20"
                
                # Processar o texto para formato RTF
                linhas = texto.split('\n')
                rtf_content = []
                for linha in linhas:
                    # Escapar caracteres especiais RTF
                    linha = linha.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}')
                    rtf_content.append(linha + '\\par')
                
                # Montar o documento RTF completo
                rtf_final = rtf_header + ' '.join(rtf_content) + '}'
                conteudo = rtf_final.encode('ascii', errors='replace')
                logger.debug("Arquivo de texto convertido para RTF")
            except Exception as e:
                logger.error(f"Erro ao converter texto para RTF: {str(e)}")
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "O arquivo deve estar no formato RTF válido"}
                )
        
        try:
            # Tentar comprimir o conteúdo
            conteudo_comprimido = zlib.compress(conteudo, level=9)  # Usar compressão máxima
            taxa_compressao = len(conteudo_comprimido) / len(conteudo)
            logger.debug(f"Taxa de compressão: {taxa_compressao:.2%}")
            
            if taxa_compressao > 0.9:  # Se a compressão não for efetiva
                logger.warning("Compressão não efetiva, arquivo pode conter dados binários")
        except Exception as e:
            logger.error(f"Erro ao comprimir conteúdo: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Erro ao processar arquivo. Verifique se é um RTF válido."}
            )
        
        db = await get_database()
        
        # Codificar em base64
        conteudo_base64 = base64.b64encode(conteudo_comprimido)
        
        novo_modelo = {
            "nome": nome_modelo,
            "titulo": titulo_documento,
            "tipo": tipo_termo,
            "arquivo": conteudo_base64,
            "comprimido": True,
            "formato": "rtf",
            "tamanho_original": len(conteudo),
            "tamanho_comprimido": len(conteudo_comprimido),
            "data_criacao": datetime.now()
        }
        
        resultado = await db.modelos.insert_one(novo_modelo)
        
        return JSONResponse(content={
            "success": True,
            "message": "Modelo cadastrado com sucesso",
            "modelo_id": str(resultado.inserted_id)
        })
        
    except Exception as e:
        logger.error(f"Erro ao cadastrar modelo: {str(e)}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erro ao cadastrar modelo: {str(e)}"}
        )

@app.get("/api/modelos-termo")
async def listar_modelos():
    try:
        db = await get_database()
        # Buscar apenas os campos necessários, excluindo o arquivo
        cursor = db.modelos.find({}, {
            "_id": 1, 
            "nome": 1, 
            "titulo": 1, 
            "tipo": 1
        })
        modelos = await cursor.to_list(length=None)
        
        # Converter ObjectId para string em cada modelo
        for modelo in modelos:
            modelo['_id'] = str(modelo['_id'])
        
        return JSONResponse(content=modelos)
        
    except Exception as e:
        logger.error(f"Erro ao listar modelos: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Erro ao listar modelos"}
        )

@app.get("/api/modelos", response_class=JSONResponse)
async def listar_modelos_completo():
    logger.debug("Acessando rota /api/modelos")
    
    try:
        db = await get_database()
        logger.debug("Conexão com banco de dados estabelecida")
        
        collection = db["modelos"]
        modelos = []
        
        
        async for documento in collection.find({}):
            logger.debug(f"Documento encontrado: {documento}")
            modelos.append({
                "_id": str(documento["_id"]),
                "nome_modelo": documento.get("nome", ""),
                "titulo_documento": documento.get("titulo", ""),
                "tipo_termo": documento.get("tipo", "N/A"),
                "arquivo": documento.get("arquivo", ""),
                "data_cadastro": documento.get("data_cadastro", "")
            })

            # Capitalizar o tipo de cada modelo
        for modelo in modelos:
            if "tipo" in modelo:
                modelo["tipo"] = modelo["tipo"].capitalize()
            modelo["_id"] = str(modelo["_id"])  # Converter ObjectId para string
            
        
        logger.debug(f"Total de modelos encontrados: {len(modelos)}")
        return {
            "success": True,
            "modelos": modelos
        }
    except Exception as e:
        logger.error(f"Erro ao listar modelos: {str(e)}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@app.get("/api/download-termo-pdf/{termo_id}")
async def download_termo_pdf(termo_id: str):
    try:
        logger.info(f"Solicitação de download do PDF para termo {termo_id}")
        db = await get_database()
        
        # Verificar se o ID é válido
        try:
            termo_object_id = ObjectId(termo_id)
        except Exception as e:
            logger.error(f"ID do termo inválido: {termo_id}")
            raise HTTPException(status_code=400, detail="ID do termo inválido")
        
        # Buscar o termo
        termo = await db.termos.find_one({"_id": termo_object_id})
        logger.info(f"Termo encontrado: {termo}")
        
        if not termo:
            logger.error(f"Termo {termo_id} não encontrado")
            raise HTTPException(status_code=404, detail="Termo não encontrado")
        
        # Buscar o arquivo do termo
        arquivo_pdf = encontrar_arquivo_termo(termo)
        if not arquivo_pdf:
            logger.error(f"Arquivo PDF não encontrado para o termo {termo_id}")
            
            # Listar arquivos disponíveis para debug
            arquivos_disponiveis = os.listdir("termos")
            logger.info(f"Arquivos disponíveis no diretório termos: {arquivos_disponiveis}")
            
            raise HTTPException(status_code=404, detail="Arquivo PDF não encontrado")
            
        # Retornar o arquivo
        logger.info(f"Enviando arquivo: {arquivo_pdf}")
        return FileResponse(
            arquivo_pdf,
            media_type="application/pdf",
            filename=os.path.basename(arquivo_pdf)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao baixar PDF: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erro ao baixar PDF: {str(e)}")

def encontrar_arquivo_termo(termo_data, diretorio="termos"):
    """
    Encontra o arquivo PDF do termo baseado nos dados do termo.
    Lida com diferentes formatos de nome e caracteres especiais.
    """
    try:
        logger.info(f"Procurando arquivo para termo: {termo_data}")
        
        # Se o termo tem o campo arquivo, usar ele diretamente
        if "arquivo" in termo_data and termo_data["arquivo"]:
            arquivo_pdf = termo_data["arquivo"]
            if os.path.exists(arquivo_pdf):
                logger.info(f"Arquivo encontrado pelo caminho direto: {arquivo_pdf}")
                return arquivo_pdf
            
            # Tentar com o caminho completo
            arquivo_pdf_completo = os.path.join(os.path.dirname(__file__), arquivo_pdf)
            if os.path.exists(arquivo_pdf_completo):
                logger.info(f"Arquivo encontrado pelo caminho completo: {arquivo_pdf_completo}")
                return arquivo_pdf_completo
        
        # Se não encontrou pelo caminho direto, tentar pelo padrão de nome
        data_str = termo_data['data_criacao'].strftime('%Y%m%d')
        nome_colaborador = termo_data.get('dados', {}).get('nome_colaborador', '')
        nome_base = unidecode(nome_colaborador.replace(' ', '_'))
        
        logger.info(f"Procurando por arquivo com data {data_str} e nome base {nome_base}")
        
        # Listar todos os arquivos no diretório
        arquivos = os.listdir(diretorio)
        logger.info(f"Arquivos encontrados no diretório: {arquivos}")
        
        # Procurar por arquivos que correspondam ao padrão
        for arquivo in arquivos:
            if arquivo.endswith('.pdf') and data_str in arquivo and nome_base in unidecode(arquivo.upper()):
                caminho_completo = os.path.join(diretorio, arquivo)
                if os.path.isfile(caminho_completo):
                    logger.info(f"Arquivo encontrado por correspondência de padrão: {caminho_completo}")
                    return caminho_completo
        
        logger.error(f"Nenhum arquivo encontrado para o termo com data {data_str} e nome {nome_base}")
        return None
        
    except Exception as e:
        logger.error(f"Erro ao buscar arquivo do termo: {str(e)}\n{traceback.format_exc()}")
        return None

@app.get("/api/listar-termos", response_class=JSONResponse)
async def listar_termos():
    try:
        logger.info("Iniciando listagem de termos")
        db = await get_database()
        if db is None:
            raise Exception("Erro ao conectar com o banco de dados")
            
        collection = db["termos"]
        termos = []

        # Buscar todos os termos ordenados por data de criação (mais recentes primeiro)
        cursor = collection.find({}).sort("data_criacao", -1)
        
        async for documento in cursor:
            # Converter ObjectId e datas para string
            termo = convert_mongo_doc(documento)
            
            # Extrair dados relevantes do documento
            termo_formatado = {
                "_id": termo["_id"],
                "titulo_documento": termo["dados"].get("titulo_documento", ""),
                "nome_colaborador": termo["dados"].get("nome_colaborador", ""),
                "data_documento": termo["dados"].get("data_documento", ""),
                "data_assinatura": termo.get("data_assinatura", ""),
                "status": termo.get("status", "Pendente"),
                "tipo": termo.get("tipo", "")
            }
            
            termos.append(termo_formatado)
            
        logger.info(f"Total de termos encontrados: {len(termos)}")
        return JSONResponse(content={
            "success": True,
            "termos": termos
        })
    except Exception as e:
        logger.error(f"Erro ao listar termos: {str(e)}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Erro ao listar termos: {str(e)}"
            }
        )

@app.get("/api/visualizar-termo/{termo_id}")
async def visualizar_termo(termo_id: str):
    try:
        logger.info(f"Acessando termo: {termo_id}")
        
        # Buscar termo no banco
        db = await get_database()
        termo = await db.termos.find_one({"_id": ObjectId(termo_id)})
        
        if not termo:
            raise HTTPException(status_code=404, detail="Termo não encontrado")
        
        # Verificar se o arquivo existe
        arquivo_path = os.path.join(TERMOS_FOLDER, termo['arquivo'])
        logger.info(f"Buscando arquivo em: {arquivo_path}")
        
        if not os.path.exists(arquivo_path):
            logger.error(f"Arquivo não encontrado: {arquivo_path}")
            raise HTTPException(status_code=404, detail="Arquivo do termo não encontrado")
        
        # Retornar o arquivo PDF
        return FileResponse(
            arquivo_path,
            media_type="application/pdf",
            filename=termo['arquivo']
        )
        
    except Exception as e:
        logger.error(f"Erro ao visualizar termo: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download-termo/{nome_arquivo}")
async def download_termo(nome_arquivo: str):
    try:
        logger.info(f"Solicitado download do arquivo: {nome_arquivo}")
        
        # Verificar se é um arquivo assinado
        if '_assinado' in nome_arquivo:
            arquivo_path = os.path.join(TERMOS_ASSINADOS_FOLDER, nome_arquivo)
        else:
            arquivo_path = os.path.join(TERMOS_FOLDER, nome_arquivo)
            
        logger.info(f"Buscando arquivo em: {arquivo_path}")
        
        if not os.path.exists(arquivo_path):
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
            
        # Verificar se o arquivo não está vazio
        if os.path.getsize(arquivo_path) == 0:
            raise HTTPException(status_code=500, detail="Arquivo está vazio")
            
        return FileResponse(
            arquivo_path,
            media_type='application/pdf',
            filename=nome_arquivo
        )
        
    except Exception as e:
        logger.error(f"Erro ao fazer download do termo: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/excluir-modelo/{modelo_id}")
async def excluir_modelo(modelo_id: str):
    try:
        logging.info(f"\n=== Excluindo modelo {modelo_id} ===")
        db = await get_database()
        resultado = await db.modelos.delete_one({"_id": ObjectId(modelo_id)})
        if resultado.deleted_count == 1:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "detail": "Modelo excluído com sucesso"
                }
            )
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "detail": "Modelo não encontrado"
                }
            )
    except Exception as e:
        msg = f"Erro ao excluir modelo {modelo_id}: {str(e)}"
        logging.error(msg)
        logging.error("Stack trace:", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": f"Erro interno do servidor: {str(e)}"
            }
        )

@app.post("/api/salvar-modelo")
async def salvar_modelo(
    nome: str = Form(...),
    descricao: str = Form(...),
    arquivo: UploadFile = File(...)
):
    try:
        logger.info(f"Salvando novo modelo: {nome}")
        
        # Ler o conteúdo do arquivo
        conteudo = await arquivo.read()
        
        # Verificar se é um arquivo RTF
        if not arquivo.filename.lower().endswith('.rtf'):
            raise HTTPException(status_code=400, detail="O arquivo deve ser um RTF")
            
        # Tentar decodificar para verificar se é um RTF válido
        try:
            conteudo_str = conteudo.decode('utf-8')
            if not conteudo_str.startswith('{\\rtf'):
                raise HTTPException(status_code=400, detail="Arquivo RTF inválido")
        except Exception as e:
            logger.error(f"Erro ao validar RTF: {str(e)}")
            raise HTTPException(status_code=400, detail="Arquivo RTF inválido")
            
        # Comprimir e codificar o conteúdo
        conteudo_comprimido = zlib.compress(conteudo)
        conteudo_base64 = base64.b64encode(conteudo_comprimido).decode('utf-8')
        
        # Criar o documento no banco
        db = await get_database()
        novo_modelo = {
            "nome": nome,
            "descricao": descricao,
            "arquivo": conteudo_base64,
            "comprimido": True,
            "data_criacao": datetime.utcnow()
        }
        
        resultado = await db.modelos.insert_one(novo_modelo)
        
        return JSONResponse({
            "success": True,
            "message": "Modelo salvo com sucesso",
            "modelo_id": str(resultado.inserted_id)
        })
        
    except HTTPException as he:
        return JSONResponse(
            status_code=he.status_code,
            content={"success": False, "message": he.detail}
        )
    except Exception as e:
        logger.error(f"Erro ao salvar modelo: {str(e)}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erro ao salvar modelo: {str(e)}"}
        )

@app.get("/buscar-termos/{nome}")
async def buscar_termos(
    nome: str,
    tipo_termo: str = Query(None)
):
    logging.info(f"Buscando termos com nome: {nome}")
    db = await get_database()
    termos = await db.termos.find({"nome_colaborador": nome}).to_list(1000)
    termos = [convert_mongo_doc(termo) for termo in termos]
    return termos


@app.get("/link-assinatura/{termo_id}")
async def gerar_link_assinatura(termo_id: str):
    try:
        logging.info(f"Tentando gerar link de assinatura para termo com ID: {termo_id}")
        db = await get_database()
        termo = await db.termos.find_one({"_id": ObjectId(termo_id)})
        
        if termo is None:
            return JSONResponse({"success": False, "message": "Termo não encontrado"})
        
        # Retorna o link usando o _id do termo
        return JSONResponse({
            "success": True,
            "message": "Link gerado com sucesso",
            "link": f"/assinar-termo/{termo_id}"
        })
    except Exception as e:
        logger.error(f"Erro ao gerar link de assinatura: {str(e)}")
        return JSONResponse({
            "success": False,
            "message": f"Erro ao gerar link de assinatura: {str(e)}"
        })

@app.post("/api/processar-termo")
async def processar_termo(
    request: Request,
    modelo_id: str = Form(...),
    dados_termo: str = Form(...)
):
    try:
        logger.info("Iniciando processamento de novo termo")
        logger.debug(f"Dados recebidos - modelo_id: {modelo_id}, dados_termo: {dados_termo}")
        
        # Conectar ao banco de dados
        db = await get_database()
        if db is None:
            raise Exception("Erro ao conectar com o banco de dados")

        # Buscar o modelo
        modelo = await db.modelos.find_one({"_id": ObjectId(modelo_id)})
        if not modelo:
            raise Exception("Modelo não encontrado")

        # Converter dados do termo de string JSON para dicionário
        dados = json.loads(dados_termo)
        
        # Gerar nome único para o arquivo RTF e PDF
        nome_colaborador_safe = dados['nome_colaborador'].replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f"termo_{timestamp}_{nome_colaborador_safe}"
        caminho_rtf = os.path.join("termos", f"{nome_arquivo}.rtf")
        caminho_pdf = os.path.join("termos", f"{nome_arquivo}.pdf")
        
        # Garantir que o diretório existe
        os.makedirs("termos", exist_ok=True)
        
        # Decodificar o arquivo RTF do modelo
        conteudo_rtf = base64.b64decode(modelo["arquivo"])
        if modelo.get("comprimido", False):
            conteudo_rtf = zlib.decompress(conteudo_rtf)
        
        try:
            # Primeiro tenta decodificar como ISO-8859-1
            conteudo_rtf_str = conteudo_rtf.decode('iso-8859-1')
        except UnicodeDecodeError:
            # Se falhar, usa UTF-8
            conteudo_rtf_str = conteudo_rtf.decode('utf-8', errors='ignore')
        
        # Substituir variáveis no RTF
        for chave, valor in dados.items():
            valor_str = str(valor)
            conteudo_rtf_str = conteudo_rtf_str.replace(chave, valor_str)
        
        # Salvar o RTF
        with open(caminho_rtf, 'wb') as f:
            f.write(conteudo_rtf_str.encode('iso-8859-1'))
            
        logger.info(f"Arquivo RTF salvo em: {caminho_rtf}")
            
        # Converter RTF para PDF
        if not await converter_rtf_para_pdf(caminho_rtf, caminho_pdf):
            # Se falhar na conversão, excluir o RTF e retornar erro
            try:
                os.remove(caminho_rtf)
            except:
                pass
            raise Exception("Erro ao converter RTF para PDF")
            
        logger.info(f"Arquivo PDF gerado em: {caminho_pdf}")
        
        # Excluir o arquivo RTF temporário
        try:
            os.remove(caminho_rtf)
            logger.info("Arquivo RTF temporário removido")
        except Exception as e:
            logger.warning(f"Erro ao remover arquivo RTF temporário: {str(e)}")
        
        # Gerar token único para o termo
        token = str(uuid.uuid4())
        
        # Criar documento do termo
        novo_termo = {
            "modelo_id": ObjectId(modelo_id),
            "dados": dados,
            "status": "Pendente",
            "data_criacao": datetime.utcnow(),
            "token": token,
            "tipo": modelo.get("tipo", ""),
            "arquivo": caminho_pdf  # Salvar o caminho do arquivo PDF
        }
        
        logger.info("Salvando termo no banco de dados...")
        logger.debug(f"Dados do termo: {novo_termo}")
        
        # Inserir termo no banco de dados
        collection = db["termos"]  # Especificar a coleção explicitamente
        resultado = await collection.insert_one(novo_termo)
        termo_id = str(resultado.inserted_id)
        
        logger.info(f"Termo criado com sucesso. ID: {termo_id}")
        return JSONResponse(content={
            "success": True,
            "termo_id": termo_id,
            "message": "Termo criado com sucesso"
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON dos dados do termo: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Dados do termo inválidos"
            }
        )
    except Exception as e:
        logger.error(f"Erro ao processar termo: {str(e)}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Erro ao processar termo: {str(e)}"
            }
        )

@app.get("/download-termo/{termo_id}")
async def download_termo(termo_id: str):
    try:
        # Estabelecer conexão com o MongoDB
        client = await get_database_client()
        db = client[DATABASE_NAME]
        termos_collection = db[TERMOS_COLLECTION]
        
        # Buscar o termo
        termo = await termos_collection.find_one({"_id": ObjectId(termo_id)})
        if not termo:
            raise HTTPException(status_code=404, detail="Termo não encontrado")
            
        # Verificar se o termo está assinado
        if not termo.get('assinado'):
            raise HTTPException(status_code=400, detail="Termo ainda não foi assinado")
            
        # Verificar se existe arquivo assinado
        if not termo.get('arquivo_assinado'):
            raise HTTPException(status_code=400, detail="Arquivo assinado não encontrado")
            
        # Preparar o arquivo para download
        content = termo['arquivo_assinado']
        filename = termo.get('nome_arquivo_assinado', 'termo_assinado.pdf')
        
        # Retornar o arquivo
        return Response(
            content=content,
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
            
    except Exception as e:
        logger.error(f"Erro ao fazer download do termo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao fazer download do termo: {str(e)}")

@app.post("/salvar-termo")
async def salvar_termo(
    nome_colaborador: str = Form(...),
    tipo: str = Form(...),
    modelo_id: str = Form(...),
    modelo_notebook: str = Form(...),
    observacoes: str = Form(None)
):
    try:
        logger.info(f"Salvando novo termo para {nome_colaborador}")
        db = await get_database()
        if not db:
            raise Exception("Não foi possível conectar ao banco de dados")

        # Gerar token único para o termo
        token = str(uuid4())
        
        # Criar documento do termo
        termo = {
            "nome_colaborador": nome_colaborador,
            "tipo": tipo,
            "modelo_id": ObjectId(modelo_id),
            "modelo_notebook": modelo_notebook,
            "observacoes": observacoes,
            "token": token,
            "status": "pendente",
            "data_criacao": datetime.now(),
            "tem_devolucao": False,
            "data_documento": datetime.now(),  # Definindo a data do documento como agora
            "data_assinatura": None,  # Nenhuma assinatura no momento da criação
            "arquivo_pdf": None  # Nenhum PDF associado no momento da criação
        }
        
        # Salvar no banco de dados
        result = await db.termos.insert_one(termo)
        
        logger.info(f"Termo salvo com sucesso. ID: {result.inserted_id}")
        
        return {
            "success": True,
            "termo_id": str(result.inserted_id),
            "message": "Termo criado com sucesso"
        }
            
    except Exception as e:
        error_msg = f"Erro ao salvar termo: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

import subprocess
import os

async def gerar_pdf_do_termo(termo_id: str, modelo_rtf: str, dados: dict):
    try:
        logger.info(f"Gerando PDF para o termo {termo_id}")
        
        # Criar diretório para termos se não existir
        termo_dir = os.path.abspath("termos")
        os.makedirs(termo_dir, exist_ok=True)
        
        # Nome do arquivo baseado no ID do termo
        nome_arquivo = f"termo_{termo_id}"
        rtf_path = os.path.join(termo_dir, f"{nome_arquivo}.rtf")
        pdf_path = os.path.join(termo_dir, f"{nome_arquivo}.pdf")
        
        # Primeiro substituir as variáveis no RTF
        rtf_processado = substituir_variaveis_rtf(modelo_rtf, dados)
        
        # Salvar RTF com encoding UTF-8
        with open(rtf_path, "w", encoding="utf-8") as f:
            f.write(rtf_processado)
            
        try:
            import pypandoc
            
            # Converter RTF para PDF usando pandoc
            logger.info("Convertendo RTF para PDF com pandoc...")
            output = pypandoc.convert_file(
                rtf_path,
                'pdf',
                outputfile=pdf_path,
                format='rtf'
            )
            
            # Verificar se o PDF foi gerado
            if not os.path.exists(pdf_path):
                logger.error("PDF não foi gerado")
                raise Exception("PDF não foi gerado corretamente")
            
            logger.info("PDF gerado com sucesso")
            
            return pdf_path
            
        except Exception as e:
            logger.error(f"Erro na conversão do PDF: {str(e)}\n{traceback.format_exc()}")
            return None
        
        finally:
            # Limpar arquivo RTF
            try:
                if os.path.exists(rtf_path):
                    os.remove(rtf_path)
                    logger.info("Arquivo RTF temporário removido")
            except Exception as e:
                logger.warning(f"Erro ao remover arquivo temporário: {str(e)}")

    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {str(e)}\n{traceback.format_exc()}")
        return None

def substituir_variaveis_rtf(rtf_content: str, dados: dict) -> str:
    """
    Substitui as variáveis no conteúdo RTF pelos valores fornecidos.
    Mantém a formatação RTF e codificação UTF-8.
    """
    try:
        # Função para normalizar caracteres especiais
        def normalizar_texto(texto):
            if not texto:
                return ""

            # Mapeamento de caracteres especiais para suas versões mais simples
            replacements = {
                '"': '"',  # U+201D (aspas curvas) para aspas retas
                '"': '"',  # U+201C (aspas curvas) para aspas retas
                ''': "'",  # aspas simples curvas para retas
                ''': "'",  # aspas simples curvas para retas
                '–': '-',  # travessão para hífen
                '—': '-',  # travessão longo para hífen
                '…': '...' # reticências para pontos
            }

            for original, replacement in replacements.items():
                texto = texto.replace(original, replacement)
            return texto

        # Processar o conteúdo RTF
        resultado = rtf_content

        # Substituir cada variável pelo seu valor
        for chave, valor in dados.items():
            valor_str = str(valor)
            resultado = resultado.replace(chave, normalizar_texto(valor_str))

        return resultado

    except Exception as e:
        logger.error(f"Erro ao substituir variáveis no RTF: {str(e)}")
        raise Exception(f"Erro ao processar template RTF: {str(e)}")

@app.get("/api/gerar-termo-devolucao/{termo_id}")
async def gerar_termo_devolucao(termo_id: str):
    try:
        logger.info(f"Gerando termo de devolução para o termo {termo_id}")
        db = await get_database()
        
        # Buscar o termo original
        termo_original = await db.termos.find_one({"_id": ObjectId(termo_id)})
        if not termo_original:
            raise HTTPException(status_code=404, detail="Termo original não encontrado")
            
        if termo_original.get("status") != "Assinado":
            raise HTTPException(status_code=400, detail="Termo precisa estar assinado para gerar devolução")
            
        # Buscar o modelo de devolução
        modelo_devolucao = await db.modelos.find_one({"tipo": "devolucao"})
        if not modelo_devolucao:
            raise HTTPException(status_code=404, detail="Modelo de devolução não encontrado")
            
        # Preparar dados para o termo de devolução
        dados_devolucao = termo_original["dados"].copy()
        dados_devolucao["data_documento"] = datetime.now().strftime("%Y-%m-%d")
        dados_devolucao["dia_mesescrito_ano"] = datetime.now().strftime("%d de %B de %Y")
        
        # Criar o termo de devolução
        novo_termo = {
            "modelo_id": modelo_devolucao["_id"],
            "dados": dados_devolucao,
            "titulo_documento": "TERMO DE DEVOLUÇÃO",
            "nome_colaborador": dados_devolucao["nome_colaborador"],
            "data_documento": dados_devolucao["data_documento"],
            "status": "Pendente de Assinatura",
            "data_criacao": datetime.utcnow(),
            "termo_original_id": termo_original["_id"]
        }
        
        # Gerar o arquivo PDF do termo de devolução
        termo_dir = "termos"
        os.makedirs(termo_dir, exist_ok=True)
        
        # Nome do arquivo baseado na data e nome do colaborador
        nome_arquivo = f"termo_devolucao_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{unidecode(dados_devolucao['nome_colaborador'].replace(' ', '_'))}.pdf"
        novo_termo["arquivo"] = os.path.join(termo_dir, nome_arquivo)
        
        # Inserir o novo termo no banco
        resultado = await db.termos.insert_one(novo_termo)
        novo_termo_id = resultado.inserted_id
        
        return JSONResponse({
            "success": True,
            "message": "Termo de devolução gerado com sucesso",
            "termo_id": str(novo_termo_id)
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar termo de devolução: {str(e)}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Erro ao gerar termo de devolução: {str(e)}"
            }
        )

@app.delete("/api/deletar-termo/{termo_id}")
async def deletar_termo(termo_id: str):
    try:
        logger.info(f"Iniciando exclusão do termo {termo_id}")
        
        # Validar o ID do termo
        if not ObjectId.is_valid(termo_id):
            raise Exception("ID do termo inválido")
            
        # Conectar ao banco de dados
        db = await get_database()
        if db is None:
            raise Exception("Erro ao conectar com o banco de dados")
            
        # Buscar o termo para verificar se existe e pegar informações
        termo = await db.termos.find_one({"_id": ObjectId(termo_id)})
        if not termo:
            raise Exception("Termo não encontrado")
            
        # Excluir arquivos locais
        try:
            # Pegar o caminho do arquivo PDF
            caminho_pdf = termo.get("arquivo")
            if caminho_pdf:
                # Gerar caminho do RTF substituindo a extensão
                caminho_rtf = os.path.splitext(caminho_pdf)[0] + ".rtf"
                
                # Excluir RTF se existir
                if os.path.exists(caminho_rtf):
                    os.remove(caminho_rtf)
                    logger.info(f"Arquivo RTF excluído: {caminho_rtf}")
                    
                # Excluir PDF se existir
                if os.path.exists(caminho_pdf):
                    os.remove(caminho_pdf)
                    logger.info(f"Arquivo PDF excluído: {caminho_pdf}")
                else:
                    logger.warning(f"Arquivo PDF não encontrado: {caminho_pdf}")
            else:
                logger.warning("Caminho do arquivo não encontrado no documento do termo")
                
        except Exception as e:
            logger.warning(f"Erro ao excluir arquivos locais: {str(e)}")
            # Continua mesmo se falhar ao excluir arquivos locais
            
        # Deletar o termo do banco de dados
        resultado = await db.termos.delete_one({"_id": ObjectId(termo_id)})
        
        if resultado.deleted_count == 1:
            logger.info(f"Termo {termo_id} deletado com sucesso")
            return JSONResponse(content={
                "success": True,
                "message": "Termo deletado com sucesso"
            })
        else:
            raise Exception("Erro ao deletar termo do banco de dados")
            
    except Exception as e:
        logger.error(f"Erro ao deletar termo: {str(e)}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Erro ao deletar termo: {str(e)}"
            }
        )

async def converter_rtf_para_pdf(arquivo_rtf: str, arquivo_pdf: str) -> bool:
    """
    Converte um arquivo RTF para PDF usando o LibreOffice.
    
    Args:
        arquivo_rtf (str): Caminho para o arquivo RTF de entrada
        arquivo_pdf (str): Caminho para o arquivo PDF de saída
    
    Returns:
        bool: True se a conversão foi bem sucedida, False caso contrário
    """
    try:
        logger.info(f"Iniciando conversão de RTF para PDF. Arquivo RTF: {arquivo_rtf}, PDF destino: {arquivo_pdf}")
        
        # Verificar se o arquivo RTF existe
        if not os.path.exists(arquivo_rtf):
            logger.error(f"Arquivo RTF não encontrado: {arquivo_rtf}")
            return False
            
        logger.info(f"Arquivo RTF encontrado. Tamanho: {os.path.getsize(arquivo_rtf)} bytes")
            
        # Garantir que o diretório de saída existe
        os.makedirs(os.path.dirname(arquivo_pdf), exist_ok=True)
        logger.info(f"Diretório de saída criado/verificado: {os.path.dirname(arquivo_pdf)}")
        
        # Caminho do executável do LibreOffice
        soffice_exec = r"C:\Program Files\LibreOffice\program\soffice.exe"
        
        if not os.path.exists(soffice_exec):
            logger.error(f"LibreOffice não encontrado em: {soffice_exec}")
            return False
            
        logger.info(f"LibreOffice encontrado em: {soffice_exec}")
        
        # Converter caminhos para absolutos
        arquivo_rtf_abs = os.path.abspath(arquivo_rtf)
        arquivo_pdf_abs = os.path.abspath(arquivo_pdf)
        diretorio_saida_abs = os.path.dirname(arquivo_pdf_abs)
        
        # Comando para converter usando o LibreOffice
        comando = [
            soffice_exec,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", diretorio_saida_abs,
            arquivo_rtf_abs
        ]
        
        logger.info(f"Executando comando: {' '.join(comando)}")
        
        # Executar o comando de forma síncrona
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            check=False  # Não lançar exceção em caso de erro
        )
        
        # Log da saída do processo
        if resultado.stdout:
            logger.info(f"Saída do LibreOffice: {resultado.stdout}")
        if resultado.stderr:
            logger.warning(f"Erro do LibreOffice: {resultado.stderr}")
        
        # Verificar se o processo foi bem sucedido
        if resultado.returncode != 0:
            logger.error(f"Erro ao converter RTF para PDF. Código de retorno: {resultado.returncode}")
            return False
            
        # O LibreOffice gera o PDF com o mesmo nome do RTF
        pdf_gerado = os.path.splitext(arquivo_rtf_abs)[0] + ".pdf"
        
        # Se o arquivo gerado não está no local desejado, mover para o local correto
        if pdf_gerado != arquivo_pdf_abs:
            logger.info(f"Movendo arquivo de {pdf_gerado} para {arquivo_pdf_abs}")
            if os.path.exists(arquivo_pdf_abs):
                os.remove(arquivo_pdf_abs)  # Remove o arquivo existente se houver
            os.rename(pdf_gerado, arquivo_pdf_abs)
        
        # Verificar se o arquivo final existe
        if not os.path.exists(arquivo_pdf_abs):
            logger.error(f"Arquivo PDF não foi gerado: {arquivo_pdf_abs}")
            return False
            
        logger.info(f"Arquivo PDF gerado com sucesso: {arquivo_pdf_abs}")
        return True
        
    except Exception as e:
        logger.error(f"Erro durante a conversão RTF para PDF: {str(e)}\n{traceback.format_exc()}")
        return False

@app.get("/api/status-termo/{termo_id}")
async def get_termo_status(termo_id: str):
    try:
        db = await get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Erro ao conectar com o banco de dados")

        termo = await db.termos.find_one({"_id": ObjectId(termo_id)})
        if not termo:
            raise HTTPException(status_code=404, detail="Termo não encontrado")

        return {
            "status": termo.get("status", "Pendente de Assinatura"),
            "arquivo_assinado": termo.get("arquivo_assinado", None),
            "data_assinatura": termo.get("data_assinatura", None)
        }

    except Exception as e:
        logger.error(f"Erro ao buscar status do termo: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

class AssinaturaData(BaseModel):
    termo_id: str
    assinatura: str
    posicao: Dict[str, float]

@app.post("/api/salvar-assinatura")
async def salvar_assinatura_api(
    termo_id: str = Form(...),
    assinatura: str = Form(...),
    posicao: str = Form(...)
):
    try:
        # Estabelecer conexão com o MongoDB
        db = await get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Erro ao conectar com o banco de dados")

        # Obter o termo original
        termo = await db.termos.find_one({'_id': ObjectId(termo_id)})
        if termo is None:
            raise HTTPException(status_code=404, detail="Termo não encontrado")

        # Converter a string posicao em dicionário
        posicao_dict = json.loads(posicao)

        # Validar dados
        if not termo_id or not assinatura or not posicao_dict:
            raise HTTPException(status_code=400, detail="Dados incompletos")

        # Remover o prefixo 'data:image/png;base64,' se presente
        if 'base64,' in assinatura:
            assinatura_base64 = assinatura.split('base64,')[1]
        else:
            assinatura_base64 = assinatura

        try:
            assinatura_bytes = base64.b64decode(assinatura_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erro ao decodificar assinatura: {str(e)}")

        # Obter o caminho do arquivo original
        nome_arquivo = termo['arquivo'].replace('termos\\', '')
        pdf_path = os.path.join(TERMOS_FOLDER, nome_arquivo)
        logger.info(f"Tentando acessar PDF em: {pdf_path}")

        if not os.path.exists(pdf_path):
            logger.error(f"Arquivo PDF não encontrado em: {pdf_path}")
            raise HTTPException(status_code=404, detail=f"Arquivo PDF não encontrado: {termo['arquivo']}")

        # Criar nome do arquivo assinado
        arquivo_assinado = nome_arquivo.replace('.pdf', '_assinado.pdf')
        output_path = os.path.join(TERMOS_ASSINADOS_FOLDER, arquivo_assinado)

        # Garantir que a pasta existe
        os.makedirs(TERMOS_ASSINADOS_FOLDER, exist_ok=True)

        try:
            # Processar a imagem da assinatura com fundo transparente
            img = Image.open(BytesIO(assinatura_bytes))
            
            # Converter para RGBA se não estiver nesse formato
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Criar máscara para tornar o fundo branco transparente
            data = img.getdata()
            new_data = []
            for item in data:
                # Se o pixel for próximo do branco (threshold de 240), torna transparente
                if item[0] > 240 and item[1] > 240 and item[2] > 240:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            img.putdata(new_data)

            # Salvar a imagem em um BytesIO
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Ler o PDF original
            pdf_doc = fitz.open(pdf_path)
            page = pdf_doc[0]

            # Usar as dimensões do A4 fornecidas pelo frontend
            page_width = float(posicao_dict.get('pageWidth', 595.276))  # A4 width em pontos
            page_height = float(posicao_dict.get('pageHeight', 841.890))  # A4 height em pontos

            # Obter coordenadas originais
            x = float(posicao_dict['x'])
            y = float(posicao_dict['y'])
            width = float(posicao_dict['width'])
            height = float(posicao_dict['height'])

            # Criar o retângulo para a imagem usando as coordenadas exatas
            img_rect = fitz.Rect(x, y, x + width, y + height)

            # Log para debug
            logger.info(f"Dimensões da página: {page_width}x{page_height}")
            logger.info(f"Posição da assinatura: x={x}, y={y}, width={width}, height={height}")
            logger.info(f"Retângulo da imagem: {img_rect}")

            # Inserir a imagem na página com as coordenadas exatas
            page.insert_image(img_rect, stream=img_bytes.getvalue(), alpha=True)

            # Salvar o PDF
            pdf_doc.save(output_path)
            pdf_doc.close()

            # Verificar se o arquivo foi criado e é válido
            if not os.path.exists(output_path):
                raise Exception("Arquivo assinado não foi criado")

            if os.path.getsize(output_path) == 0:
                raise Exception("Arquivo assinado está vazio")

            # Atualizar o termo no banco de dados
            result = await db.termos.update_one(
                {'_id': ObjectId(termo_id)},
                {
                    '$set': {
                        'arquivo_assinado': arquivo_assinado,
                        'data_assinatura': datetime.now(),
                        'status': 'Assinado'
                    }
                }
            )

            if result.modified_count == 0:
                raise Exception("Não foi possível atualizar o status do termo")

            return JSONResponse(content={
                "success": True,
                "message": "Assinatura salva com sucesso",
                "arquivo_assinado": arquivo_assinado
            })

        except Exception as e:
            # Se algo der errado, remover o arquivo se ele foi criado
            if os.path.exists(output_path):
                os.remove(output_path)
            raise Exception(f"Erro ao salvar arquivo assinado: {str(e)}")

    except Exception as e:
        logger.error(f"Erro ao salvar assinatura: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-termo")
async def upload_termo(
    arquivo: UploadFile = File(...),
    titulo: str = Form(...),
    descricao: str = Form(...)
):
    try:
        logger.info(f"Iniciando upload do termo: {titulo}")

        # Validar extensão do arquivo
        if not arquivo.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Apenas arquivos PDF são permitidos")

        # Gerar nome único para o arquivo
        arquivo_nome = f"{uuid.uuid4().hex}_{arquivo.filename}"
        arquivo_path = os.path.join(TERMOS_FOLDER, arquivo_nome)

        logger.info(f"Salvando arquivo em: {arquivo_path}")

        # Garantir que a pasta existe
        os.makedirs(TERMOS_FOLDER, exist_ok=True)

        # Salvar o arquivo
        try:
            contents = await arquivo.read()
            with open(arquivo_path, 'wb') as f:
                f.write(contents)
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo: {str(e)}")
            raise HTTPException(status_code=500, detail="Erro ao salvar arquivo")

        # Criar documento no MongoDB
        db = await get_database()
        novo_termo = {
            "titulo": titulo,
            "descricao": descricao,
            "arquivo": arquivo_nome,  
            "status": "Pendente",
            "data_criacao": datetime.now()
        }

        resultado = await db.termos.insert_one(novo_termo)

        if not resultado.inserted_id:
            # Se falhou ao inserir no banco, remover o arquivo
            os.remove(arquivo_path)
            raise HTTPException(status_code=500, detail="Erro ao salvar termo no banco de dados")

        logger.info(f"Termo criado com sucesso. ID: {resultado.inserted_id}")

        return JSONResponse(content={
            "message": "Termo criado com sucesso",
            "id": str(resultado.inserted_id)
        })

    except Exception as e:
        logger.error(f"Erro ao criar termo: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/assinar-termo/{termo_id}")
async def assinar_termo(request: Request, termo_id: str):
    try:
        logger.info(f"Acessando página de assinatura para termo: {termo_id}")

        # Estabelecer conexão com o MongoDB
        client = await get_database_client()
        db = client[DATABASE_NAME]
        termos_collection = db[TERMOS_COLLECTION]

        # Buscar o termo
        termo = await termos_collection.find_one({"_id": ObjectId(termo_id)})
        if not termo:
            raise HTTPException(status_code=404, detail="Termo não encontrado")

        return templates.TemplateResponse(
            "assinar_termo.html",
            {
                "request": request,
                "ja_assinado": termo.get('assinado', False)
            }
        )
    except Exception as e:
        logger.error(f"Erro ao acessar página de assinatura: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/termo/{termo_id}")
async def get_termo_pdf(termo_id: str):
    try:
        logger.info(f"Buscando PDF do termo: {termo_id}")

        # Buscar termo no banco
        db = await get_database()
        termo = await db.termos.find_one({"_id": ObjectId(termo_id)})

        if not termo:
            logger.error(f"Termo não encontrado: {termo_id}")
            raise HTTPException(status_code=404, detail="Termo não encontrado")

        # Se o termo está assinado e tem arquivo assinado, retornar o PDF assinado
        if termo.get('status') == 'Assinado' and termo.get('arquivo_assinado'):
            arquivo_path = os.path.join(TERMOS_ASSINADOS_FOLDER, termo['arquivo_assinado'])
            logger.info(f"Retornando PDF assinado: {arquivo_path}")
        else:
            # Caso contrário, retornar o PDF original
            nome_arquivo = termo['arquivo'].replace('termos\\', '')
            arquivo_path = os.path.join(TERMOS_FOLDER, nome_arquivo)
            logger.info(f"Retornando PDF original: {arquivo_path}")

        if not os.path.exists(arquivo_path):
            logger.error(f"Arquivo não encontrado: {arquivo_path}")
            raise HTTPException(status_code=404, detail="Arquivo do termo não encontrado")

        # Retornar o arquivo PDF
        return FileResponse(
            arquivo_path,
            media_type="application/pdf",
            filename=os.path.basename(arquivo_path)
        )

    except Exception as e:
        logger.error(f"Erro ao buscar PDF do termo: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/salvar-assinatura")
async def salvar_assinatura(request: Request):
    try:
        form_data = await request.form()
        termo_id = form_data.get('termo_id')
        assinatura_data = form_data.get('assinatura')
        posicao = json.loads(form_data.get('posicao'))

        # Validar dados recebidos
        if not termo_id or not assinatura_data or not posicao:
            return jsonify({'error': 'Dados incompletos'}), 400

        # Estabelecer conexão com o MongoDB
        client = await get_database_client()
        db = client[DATABASE_NAME]
        termos_collection = db[TERMOS_COLLECTION]

        # Obter o termo original
        termo = await termos_collection.find_one({'_id': ObjectId(termo_id)})
        if not termo:
            return jsonify({'error': 'Termo não encontrado'}), 404

        # Converter a assinatura base64 para imagem
        assinatura_img_data = base64.b64decode(assinatura_data.split(',')[1])
        assinatura_img = Image.open(BytesIO(assinatura_img_data))

        # Redimensionar a assinatura mantendo a proporção
        assinatura_width = int(posicao['width'])
        assinatura_height = int(posicao['height'])
        assinatura_img = assinatura_img.resize((assinatura_width, assinatura_height), Image.Resampling.LANCZOS)

        # Salvar a assinatura temporariamente
        temp_sig = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        assinatura_img.save(temp_sig, format='PNG')
        temp_sig.close()

        # Abrir o PDF original
        pdf_original = PyPDF2.PdfReader(BytesIO(termo['arquivo']))
        primeira_pagina = pdf_original.pages[0]

        # Obter dimensões da página
        mediabox = primeira_pagina.mediabox
        page_width = float(mediabox.width)
        page_height = float(mediabox.height)

        # Calcular a posição em coordenadas do PDF
        x = float(posicao['x'])
        y = page_height - float(posicao['y']) - assinatura_height

        # Criar um PDF temporário com a assinatura usando reportlab
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=(page_width, page_height))
        c.drawImage(temp_sig.name, x, y, width=assinatura_width, height=assinatura_height, mask='auto')
        c.save()
        packet.seek(0)

        # Criar o PDF final
        output = PyPDF2.PdfWriter()
        watermark = PyPDF2.PdfReader(packet)

        # Adicionar a primeira página e mesclar com a assinatura
        primeira_pagina.merge_page(watermark.pages[0])
        output.add_page(primeira_pagina)

        # Adicionar as demais páginas
        for i in range(1, len(pdf_original.pages)):
            output.add_page(pdf_original.pages[i])

        # Gerar o PDF final
        output_buffer = BytesIO()
        output.write(output_buffer)
        pdf_assinado = output_buffer.getvalue()

        # Limpar arquivo temporário
        os.unlink(temp_sig.name)

        # Atualizar o documento no MongoDB
        novo_nome = f"{termo['nome']}_assinado.pdf"
        termos_collection.update_one(
            {'_id': ObjectId(termo_id)},
            {
                '$set': {
                    'arquivo_assinado': pdf_assinado,
                    'nome_arquivo_assinado': novo_nome,
                    'assinado': True,
                    'data_assinatura': datetime.now()
                }
            }
        )

        return jsonify({
            'message': 'Assinatura aplicada com sucesso',
            'arquivo_assinado': str(termo_id)
        })

    except Exception as e:
        print(f"Erro ao salvar assinatura: {str(e)}")
        return jsonify({'error': f'Erro ao processar assinatura: {str(e)}'}), 500

@app.get("/api/qrcode/{termo_id}")
async def gerar_qrcode_assinatura(termo_id: str):
    try:
        # Gerar URL para assinatura mobile
        base_url = "http://localhost:8000"  
        url_assinatura = f"{base_url}/assinar-termo/{termo_id}?mobile=true"
        
        # Criar QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url_assinatura)
        qr.make(fit=True)

        # Criar imagem do QR Code
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Salvar em um buffer
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        return Response(
            content=img_buffer.getvalue(),
            media_type="image/png"
        )
    except Exception as e:
        logger.error(f"Erro ao gerar QR Code: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
