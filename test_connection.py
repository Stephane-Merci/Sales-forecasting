import mongoengine
from mongoengine import connect, Document, StringField, IntField
from datetime import datetime

def test_mongodb_connection():
    try:
        # Connect to MongoDB
        connect(
            alias='default',
            db='sales_forecasting',
            host='localhost',
            port=27017,
            name='sales_forecasting'
        )
        print("Successfully connected to MongoDB!")

        # Test Document
        class TestDocument(Document):
            name = StringField(required=True)
            value = IntField(required=True)
            created_at = StringField(default=str(datetime.now()))

            meta = {'collection': 'test_collection'}

        # Create a test document
        test_doc = TestDocument(name="test", value=1)
        test_doc.save()
        print("Successfully created test document!")
        print("Document ID:", test_doc.id)
        
        # Clean up
        test_doc.delete()
        print("Test document cleaned up successfully")
        
        return True
    except Exception as e:
        print("Error:", str(e))
        return False

if __name__ == "__main__":
    test_mongodb_connection() 