from pinecone import Pinecone, ServerlessSpec, PodSpec
import time
from django.conf import settings

pinecone_api_key = settings.PINECONE_API_KEY
use_serverless = True
pc = Pinecone(api_key=pinecone_api_key)  

if use_serverless:  
    spec = ServerlessSpec(cloud='aws', region='us-east-1')  
else:  
    # if not using a starter index, you should specify a pod_type too  
    spec = PodSpec()  
# check for and delete index if already exists  
index_name = 'podcasts'  
if index_name in pc.list_indexes().names():  
    pc.delete_index(index_name)  
# create a new index  
pc.create_index(  
    index_name,  
    dimension=1536,  # dimensionality of text-embedding-ada-002  
    metric='cosine',  
    spec=spec  
)  
# wait for index to be initialized  
while not pc.describe_index(index_name).status['ready']:  
    time.sleep(1)  

print(f"Pinecone index: {index_name} created successfully")
index = pc.Index('podcasts')
print(index.describe_index_stats())

