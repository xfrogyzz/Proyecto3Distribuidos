import os
import time
import logging
from pymongo import MongoClient
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from elasticsearch.exceptions import ConnectionError as ESConnectionError
from pymongo.errors import ConnectionFailure

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuración desde variables de entorno ---
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_DB = os.getenv("MONGO_DB", "waze_db")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "eventos_homogeneizados")

ELASTIC_HOST = os.getenv("ELASTIC_HOST", "localhost")
ELASTIC_PORT = int(os.getenv("ELASTIC_PORT", 9200))
ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "waze_events")

def wait_for_mongo(host, port, retries=10, delay=5):
    """Espera a que MongoDB esté disponible."""
    logging.info(f"Esperando a MongoDB en {host}:{port}...")
    for i in range(retries):
        try:
            client = MongoClient(host, port, serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            logging.info("Conexión con MongoDB exitosa.")
            return client
        except ConnectionFailure:
            logging.warning(f"Intento {i+1}/{retries}: MongoDB no está listo. Reintentando en {delay}s...")
            time.sleep(delay)
    logging.error("No se pudo conectar a MongoDB.")
    return None

def wait_for_elastic(host, port, retries=15, delay=10):
    """Espera a que Elasticsearch esté disponible."""
    logging.info(f"Esperando a Elasticsearch en {host}:{port}...")
    for i in range(retries):
        try:
            es_client = Elasticsearch([{'host': host, 'port': port, 'scheme': 'http'}])
            if es_client.ping():
                logging.info("Conexión con Elasticsearch exitosa.")
                return es_client
        except ESConnectionError:
            logging.warning(f"Intento {i+1}/{retries}: Elasticsearch no está listo. Reintentando en {delay}s...")
            time.sleep(delay)
    logging.error("No se pudo conectar a Elasticsearch.")
    return None

def create_index_with_mapping(es_client, index_name):
    """Crea un índice en Elasticsearch con un mapeo específico para los datos de Waze."""
    if es_client.indices.exists(index=index_name):
        logging.info(f"El índice '{index_name}' ya existe. No se creará de nuevo.")
        return

    mapping = {
        "properties": {
            "id_original": {"type": "keyword"},
            "tipo_waze_original": {"type": "keyword"},
            "location": {"type": "geo_point"}, # Campo geoespacial para mapas
            "timestamp_evento": {"type": "date"},
            "timestamp_scrape": {"type": "date"},
            "tipo_incidente_general": {"type": "keyword"}, # Ideal para agregaciones
            "subtipo_incidente": {"type": "keyword"},
            "descripcion": {"type": "text", "analyzer": "spanish"},
            "confianza": {"type": "integer"},
            "fiabilidad": {"type": "integer"},
            "comuna": {"type": "keyword"}, # Ideal para agregaciones
            "velocidad_kmh": {"type": "float"},
            "retraso_segundos": {"type": "integer"},
            "dia_semana_evento": {"type": "integer"},
            "hora_dia_evento": {"type": "integer"}
        }
    }
    
    try:
        logging.info(f"Creando índice '{index_name}' con mapeo personalizado.")
        es_client.indices.create(index=index_name, mappings=mapping)
    except Exception as e:
        logging.error(f"Error al crear el índice '{index_name}': {e}")
        raise

def mongo_to_elastic():
    """Proceso principal para migrar datos de MongoDB a Elasticsearch."""
    mongo_client = wait_for_mongo(MONGO_HOST, MONGO_PORT)
    es_client = wait_for_elastic(ELASTIC_HOST, ELASTIC_PORT)

    if not mongo_client or not es_client:
        logging.error("Proceso de importación abortado debido a problemas de conexión.")
        return

    create_index_with_mapping(es_client, ELASTIC_INDEX)

    db = mongo_client[MONGO_DB]
    collection = db[MONGO_COLLECTION]

    # Contar documentos a procesar
    total_docs = collection.count_documents({})
    if total_docs == 0:
        logging.warning("No hay documentos en la colección de MongoDB para importar. Finalizando.")
        return
    logging.info(f"Se encontraron {total_docs} documentos para importar a Elasticsearch.")

    def generate_actions():
        cursor = collection.find({}, no_cursor_timeout=True)
        for doc in cursor:
            # Transforma el documento para Elasticsearch
            source = {k: v for k, v in doc.items() if k != '_id'}
            
            # Crea el campo geo_point combinando latitud y longitud
            if 'latitud' in source and 'longitud' in source:
                source['location'] = {
                    "lat": source['latitud'],
                    "lon": source['longitud']
                }
                # Elimina los campos originales si no los quieres duplicados
                del source['latitud']
                del source['longitud']
            
            yield {
                "_index": ELASTIC_INDEX,
                "_id": doc.get("id_original", str(doc["_id"])),
                "_source": source
            }
        cursor.close()

    try:
        logging.info("Iniciando la carga masiva (bulk) de datos a Elasticsearch...")
        success, failed = bulk(es_client, generate_actions(), chunk_size=1000, request_timeout=60)
        logging.info(f"Proceso de carga finalizado. Documentos exitosos: {success}, Fallidos: {failed}")
        if failed > 0:
            logging.warning("Algunos documentos no pudieron ser indexados.")
    except Exception as e:
        logging.error(f"Error durante la carga masiva (bulk): {e}")
    finally:
        mongo_client.close()

if __name__ == "__main__":
    logging.info("Iniciando el script de importación de MongoDB a Elasticsearch...")
    mongo_to_elastic()
    logging.info("Script de importación finalizado.")