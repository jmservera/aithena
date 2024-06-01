#!/bin/sh

collection='http://localhost:8983/solr/books/config'


# add the langid processor, needs MODULES=langid in solrconfig.xml 
# <updateRequestProcessorChain name="langid" default="${update.autoCreateFields:true}"
#            processor="uuid,remove-blank,field-name-mutating,parse-boolean,parse-long,parse-double,parse-date,add-schema-fields">
#        <processor class="org.apache.solr.update.processor.LangDetectLanguageIdentifierUpdateProcessorFactory">
#          <str name="langid.fl">content,_text_</str>
#          <str name="langid.langField">language_s</str>
#          <str name="langid.fallback">en</str>
# <!--         <str name="langid.model">langdetect-183.bin</str> -->
#        </processor>
# <!--       <processor class="solr.IgnoreFieldUpdateProcessorFactory" />-->
#        <processor class="solr.LogUpdateProcessorFactory" />
#        <processor class="solr.DistributedUpdateProcessorFactory"/>
#        <processor class="solr.RunUpdateProcessorFactory" />
# </updateRequestProcessorChain>

# cannot be done with config api https://solr.apache.org/guide/solr/latest/configuration-guide/config-api.html#updaterequestprocessorchain-elements


# add the pdf extraction handler, needs SOLR_MODULES=extraction in solrconfig.xml
curl -X POST -H 'Content-type:application/json' -d '{
  "create-requesthandler": {
    "name": "/update/extract",
    "class": "solr.extraction.ExtractingRequestHandler",
    "defaults":{ "lowernames": "true", "fmap.content":"_text_", "captureAttr":"true", "update.chain":"langid"}
  }
}' $collection

curl -X POST -H 'Content-type:application/json' -d '"initParams": {
    "my-init": {
      "name": "my-init",
      "path": "/select,/browse",
      "defaults": {
        "df": "content"
      }
    }
  }' $collection
