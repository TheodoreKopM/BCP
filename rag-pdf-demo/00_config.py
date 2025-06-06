# Databricks notebook source
# MAGIC %md # POC configuration

# COMMAND ----------

# MAGIC %pip install -U -qqqq databricks-agents mlflow mlflow-skinny databricks-vectorsearch databricks-sdk langchain==0.2.1 langchain_core==0.2.5 langchain_community==0.2.4 
# MAGIC #solo la primera ejecución es necesaria para que el agente de MLflow funcione
# MAGIC #dbutils.library.restartPython()

# COMMAND ----------

#from databricks.sdk import WorkspaceClient
#from databricks.sdk.runtime import spark,dbutils
import mlflow

# COMMAND ----------

# MAGIC %run "/Workspace/Users/theodore.kop@databricks.com/BCP/Documentation_RAG/GeniaPOC/BCP/00_global_config"

# COMMAND ----------

print(f"POC app using the UC catalog/schema {UC_CATALOG}.{UC_SCHEMA} with source data from {SOURCE_PATH} synced to the Vector Search endpoint {VECTOR_SEARCH_ENDPOINT}.  \n\nChain model will be logged to UC as {UC_CATALOG}.{UC_SCHEMA}.{UC_MODEL_NAME}.  \n\nUsing MLflow Experiment `{MLFLOW_EXPERIMENT_NAME}` with data pipeline run name `{POC_DATA_PIPELINE_RUN_NAME}` and chain run name `{POC_CHAIN_RUN_NAME}`")

# COMMAND ----------

# MAGIC %md 
# MAGIC
# MAGIC # POC Configuration

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data preparation
# MAGIC ### Config
# MAGIC
# MAGIC Databricks reccomends starting with the default settings below for your POC.  Once you have collected stakeholder feedback, you will iterate on the app's quality using these parameters.
# MAGIC
# MAGIC To learn more about these settings, visit [link to guide].
# MAGIC
# MAGIC By default, we use [GTE Embeddings](https://docs.databricks.com/en/generative-ai/create-query-vector-search.html#call-a-bge-embeddings-model-using-databricks-model-serving-notebook) that is available on [Databricks Foundation Model APIs](https://docs.databricks.com/en/machine-learning/foundation-models/index.html).  GTE is a high quality open source embedding model with a large context window.  We have selected a tokenizer and chunk size that matches this embedding model.

# COMMAND ----------

data_pipeline_config = {
    # Vector Search index configuration
    "vectorsearch_config": {
        "pipeline_type": "CONTINUOUS",
    },
    # Embedding model to use
    "embedding_config": {
        # Model Serving endpoint name
        #"embedding_endpoint_name": "databricks-gte-large-en",
        "embedding_endpoint_name": "databricks-bge-large-en",
        "embedding_tokenizer": {
            # Name of the embedding model that the tokenizer recognizes
            "tokenizer_model_name": "BAAI/bge-large-en-v1.5",
            # Name of the tokenizer, either `hugging_face` or `tiktoken`
            "tokenizer_source": "hugging_face",
        },
    },
    # Parsing and chunking configuration
    "pipeline_config": {
        # File format of the source documents
        "file_format": "pdf",
        "parser": {"name": "pypdf", "config": {}},
        "chunker": {
            "name": "langchain_recursive_char",
            "config": {
                "chunk_size_tokens": 1024,
                "chunk_overlap_tokens": 512,
            },
        },
    },
}

# COMMAND ----------

# MAGIC %md
# MAGIC ### Output tables
# MAGIC
# MAGIC Next, we configure the output Delta Tables and Vector Index where the data pipeline will write the parsed/chunked/embedded data.

# COMMAND ----------

# Names of the output Delta Tables tables & Vector Search index
destination_tables_config = {
    # Staging table with the raw files & metadata
    "raw_files_table_name": f"`{UC_CATALOG}`.`{UC_SCHEMA}`.`{RAG_APP_NAME}_poc_raw_files_bronze`",
    # Parsed documents
    "parsed_docs_table_name": f"`{UC_CATALOG}`.`{UC_SCHEMA}`.`{RAG_APP_NAME}_poc_parsed_docs_silver`",
    # Chunked documents that are loaded into the Vector Index
    "chunked_docs_table_name": f"`{UC_CATALOG}`.`{UC_SCHEMA}`.`{RAG_APP_NAME}_poc_chunked_docs_gold`",
    # Destination Vector Index
    "vectorsearch_index_table_name": f"`{UC_CATALOG}`.`{UC_SCHEMA}`.`{RAG_APP_NAME}_poc_chunked_docs_gold_index`",
}
destination_tables_config["vectorsearch_index_name"] = destination_tables_config["vectorsearch_index_table_name"].replace("`", "")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Load config
# MAGIC
# MAGIC This step loads the configuration so that the `02_poc_data_preperation` Notebook can use it.

# COMMAND ----------

import json

vectorsearch_config = data_pipeline_config['vectorsearch_config']
embedding_config = data_pipeline_config['embedding_config']
pipeline_config = data_pipeline_config['pipeline_config']

print(f"Using POC data pipeline config: {json.dumps(data_pipeline_config, indent=4)}\n")
print(f"Writing to: {json.dumps(destination_tables_config, indent=4)}\n")

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC # Chain config
# MAGIC
# MAGIC Next, we configure the chain's default settings.  The chain's code has been parameterized to use these variables. 
# MAGIC
# MAGIC Again, Databricks reccomends starting with the default settings below for your POC.  Once you have collected stakeholder feedback, you will iterate on the app's quality using these parameters.
# MAGIC
# MAGIC By default, we use `databricks-dbrx-instruct` but you can change this to any LLM hosted using Databricks Model Serving, including Azure OpenAI / OpenAI models.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Single or multi turn conversation?
# MAGIC
# MAGIC Let's take a sample converastion:
# MAGIC
# MAGIC > User: What is RAG?<br/>
# MAGIC > Assistant: RAG is a technique...<br/>
# MAGIC > User: How do I do it?<br/>
# MAGIC
# MAGIC A multi-turn conversation chain allows the assistant to understand that *it* in *how do I do it?* refers to *RAG*.  A single-turn conversation chain would not understand this context, as it treats every request as a completely new question.
# MAGIC
# MAGIC Most RAG use cases are for multi-turn conversation, however, the additional step required to understand *how do I do it?* uses an LLM and thus adds a small amount of latency.

# COMMAND ----------

# Notebook with the chain's code.  Choose one based on your requirements.  
# If you are not sure, use the `multi_turn_rag_chain`.

# CHAIN_CODE_FILE = "single_turn_rag_chain"

CHAIN_CODE_FILE = "multi_turn_rag_chain"

# COMMAND ----------

VECTOR_SEARCH_ENDPOINT = "bcp_document_store"
VECTOR_SEARCH_INDEX = "theodore_kop_personal.bcp.bcp_documetn_rag_poc_chunked_docs_managed_index"

# Chain configuration
# We suggest using these default settings
rag_chain_config = {
    "databricks_resources": {
        "vector_search_endpoint_name": VECTOR_SEARCH_ENDPOINT,
        "llm_endpoint_name": "bcp-llama4-maverick",
    },
    "retriever_config": {
        "vector_search_index": VECTOR_SEARCH_INDEX,
        "schema": {
            # The column name in the retriever's response referred to the unique key
            # If using Databricks vector search with delta sync, this should the column of the delta table that acts as the primary key
            "primary_key": "chunk_id",
            # The column name in the retriever's response that contains the returned chunk.
            "chunk_text": "chunked_text",
            # The template of the chunk returned by the retriever - used to format the chunk for presentation to the LLM.
            "document_uri": "path",
        },
        # Prompt template used to format the retrieved information to present to the LLM to help in answering the user's question
        "chunk_template": "Passage: {chunk_text}\n",
        # The column name in the retriever's response that refers to the original document.
        "parameters": {
            # Number of search results that the retriever returns
            "k": 8,
            # Type of search to run
            # Semantic search: `ann`
            # Hybrid search (keyword + sementic search): `hybrid`
            "query_type": "hybrid",
        },
        # Tag for the data pipeline, allowing you to easily compare the POC results vs. future data pipeline configurations you try.
        "data_pipeline_tag": "bcp_doc_poc",
    },
    "llm_config": {
        # Define a template for the LLM prompt.  This is how the RAG chain combines the user's question and the retrieved context.
        "llm_system_prompt_template": """You are an insightful and helpful assistant for BCP that only answers questions related to BCP internal documentation. Use the following pieces of retrieved context to answer the question. Some pieces of context may be irrelevant, in which case you should not use them to form the answer. Answer honestly and if you do not now the answer or if the answer is not contained in the documentation provided as context, limit yourself to answer that "You could not find the answer in the documentation and prompt the user to provide more details"

        Context: {context}""".strip(),
                "llm_parameters": {"temperature": 0, "max_tokens": 2000},
    },
    "input_example": {
        "messages": [
            {
                "role": "user",
                "content": "Qué es un EDV?",
            },
        ]
    },
}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load config & save to YAML
# MAGIC
# MAGIC This step saves the configuration so that the `03_deploy_poc_to_review_app` Notebook can use it.

# COMMAND ----------

import yaml
print(f"Using chain config: {json.dumps(rag_chain_config, indent=4)}\n\n Using chain file: {CHAIN_CODE_FILE}")

with open('rag_chain_config.yaml', 'w') as f:
    yaml.dump(rag_chain_config, f)

# COMMAND ----------

# MAGIC %md ## Load shared utilities used by the other notebooks

# COMMAND ----------

# MAGIC %run ../z_shared_utilities
