# api/index.py
from flask import Flask, request, jsonify
from textblob import TextBlob
from transformers import pipeline, AutoTokenizer
import numpy as np
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Initialize the Hugging Face sentiment analysis pipeline and tokenizer
MODEL_NAME = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
sentiment_pipeline = pipeline("sentiment-analysis", model=MODEL_NAME)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def chunk_text(text, max_length=512):
    """Split text into chunks that respect sentence boundaries when possible."""
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_tokens = len(tokenizer.encode(sentence))
        
        if current_length + sentence_tokens <= max_length:
            current_chunk.append(sentence)
            current_length += sentence_tokens
        else:
            if current_chunk:
                chunks.append('. '.join(current_chunk) + '.')
            current_chunk = [sentence]
            current_length = sentence_tokens
    
    if current_chunk:
        chunks.append('. '.join(current_chunk) + '.')
    
    return chunks

@app.route('/api/analyze', methods=['POST'])
def analyze_sentiment():
    """Endpoint to analyze sentiment."""
    try:
        data = request.get_json()
        if 'text' not in data:
            return jsonify({'error': 'Text not provided'}), 400

        text = data['text']
        method = data.get('method', 'textblob').lower()

        if method == 'textblob':
            analysis = TextBlob(text)
            sentiment = analysis.sentiment
            result = {
                'method': 'textblob',
                'polarity': sentiment.polarity,
                'subjectivity': sentiment.subjectivity,
                'sentiment': (
                    'Positive' if sentiment.polarity > 0 else
                    'Negative' if sentiment.polarity < 0 else
                    'Neutral'
                )
            }

        elif method == 'transformers':
            chunks = chunk_text(text)
            chunk_results = []
            for chunk in chunks:
                chunk_result = sentiment_pipeline(chunk)[0]
                chunk_results.append({
                    'label': chunk_result['label'],
                    'score': chunk_result['score']
                })
            
            positive_chunks = sum(1 for r in chunk_results if r['label'] == 'POSITIVE')
            negative_chunks = sum(1 for r in chunk_results if r['label'] == 'NEGATIVE')
            
            avg_positive_score = np.mean([r['score'] for r in chunk_results if r['label'] == 'POSITIVE']) if positive_chunks > 0 else 0
            avg_negative_score = np.mean([r['score'] for r in chunk_results if r['label'] == 'NEGATIVE']) if negative_chunks > 0 else 0
            
            result = {
                'method': 'transformers',
                'positive_chunks': positive_chunks,
                'negative_chunks': negative_chunks,
                'total_chunks': len(chunk_results),
                'avg_positive_score': float(avg_positive_score),
                'avg_negative_score': float(avg_negative_score),
                'overall_sentiment': 'Positive' if positive_chunks > negative_chunks else 'Negative',
                'chunk_details': chunk_results
            }

        else:
            return jsonify({'error': 'Invalid method specified. Use "textblob" or "transformers".'}), 400

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500