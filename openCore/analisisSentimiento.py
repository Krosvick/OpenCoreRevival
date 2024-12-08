import json
import os
from collections import Counter

from transformers import pipeline


def initialize_sentiment_analyzer():
    """
    Initializes the sentiment analyzer by loading the pre-trained model.

    Returns:
        A sentiment analysis pipeline object.
    """
    return pipeline(
        model="lxyuan/distilbert-base-multilingual-cased-sentiments-student"
    )


def analizar_sentimientos_transformers(texto, clasificador_sentimientos):
    """
    Analyzes the overall sentiment of a given text using a sentiment classifier.
    Processes the text in chunks to handle long articles while maintaining context.

    Args:
        texto (str): The text to be analyzed.
        clasificador_sentimientos: The sentiment classifier.

    Returns:
        str: The overall sentiment ("Positivo", "Negativo", or "Neutro")
    """
    # Initialize counters for sentiment scores
    sentiment_scores = {
        "positive": 0.0,
        "negative": 0.0,
        "neutral": 0.0
    }
    
    # Split text into chunks of roughly 500 characters at sentence boundaries
    sentences = texto.split('.')
    current_chunk = ""
    chunk_count = 0
    
    for sentence in sentences:
        if len(sentence.strip()) == 0:
            continue
            
        if len(current_chunk) + len(sentence) < 500:
            current_chunk += sentence + "."
        else:
            if current_chunk:
                try:
                    result = clasificador_sentimientos(current_chunk)[0]
                    sentiment_scores[result['label']] += result['score']
                    chunk_count += 1
                except Exception as e:
                    print(f"Error analyzing chunk: {e}")
            current_chunk = sentence + "."
    
    # Process the last chunk
    if current_chunk:
        try:
            result = clasificador_sentimientos(current_chunk)[0]
            sentiment_scores[result['label']] += result['score']
            chunk_count += 1
        except Exception as e:
            print(f"Error analyzing final chunk: {e}")
    
    # If no valid chunks were processed, return Neutro
    if chunk_count == 0:
        return "Neutro"
    
    # Average the scores
    for sentiment in sentiment_scores:
        sentiment_scores[sentiment] /= chunk_count
    
    # Determine overall sentiment based on highest average score
    max_sentiment = max(sentiment_scores.items(), key=lambda x: x[1])
    
    # Map to Spanish sentiment labels with a minimum confidence threshold
    if max_sentiment[1] < 0.4:  # If confidence is low, return neutral
        return "Neutro"
    elif max_sentiment[0] == "positive":
        return "Positivo"
    elif max_sentiment[0] == "negative":
        return "Negativo"
    else:
        return "Neutro"


def main():
    with open("cleaned_news.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    # Filter objects that have all required fields
    valid_data = [
        item for item in data 
        if all(key in item and item[key] 
        for key in ['image_url', 'title', 'content', 'link'])
    ]

    clasificador_sentimientos = initialize_sentiment_analyzer()

    for item in valid_data:
        print("------------------------------")
        print(f"Titulo: {item['title']} ")
        texto = item["content"]
        item["sentiment"] = analizar_sentimientos_transformers(
            texto, clasificador_sentimientos
        )
        print(f"Sentimiento: {item['sentiment']} ")

    with open("newsdb.json", "w", encoding="utf-8") as f:
        json.dump(valid_data, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
