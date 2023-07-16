#!/usr/bin/env python
# encoding: utf-8

# https://python.langchain.com/docs/ecosystem/integrations/llamacpp


from langchain.embeddings import LlamaCppEmbeddings
llama = LlamaCppEmbeddings(model_path="/llama/models/7B/ggml-model-f16.bin")

import json
from flask import Flask, request, jsonify

app = Flask(__name__)
@app.route('/', methods=['GET'])
def index():
    print("loading text")
    text = request.args.get('text')
    print(text)
    query_result = llama.embed_query(text)
    return jsonify(query_result)
    # return json.dumps({'name': 'hello',
    #                    'email': 'world'})

@app.route('/', methods=['POST'])
def update_record():
    record = json.loads(request.data)

    text = record['text']
    query_result = llama.embed_query(text)
    return jsonify(query_result)

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5000)