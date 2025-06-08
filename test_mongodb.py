import mongoengine
from mongoengine import connect, Document, StringField, IntField
from datetime import datetime

# Connect to MongoDB
connect(
    alias='default',
    db='sales_forecasting',
    host='localhost',
    port=27017,
    name='sales_forecasting'
)

# Test Document
class TestDocument(Document):
    name = StringField(required=True)
    value = IntField(required=True)
    created_at = StringField(default=str(datetime.now()))

    meta = {'collection': 'test_collection'}

# Test the connection
try:
    # Create a test document
    test_doc = TestDocument(name="test", value=1)
    test_doc.save()
    print("Successfully connected to MongoDB!")
    print("Test document created with ID:", test_doc.id)
    
    # Clean up test document
    test_doc.delete()
    print("Test document cleaned up successfully")
except Exception as e:
    print("Error connecting to MongoDB:", str(e)) 