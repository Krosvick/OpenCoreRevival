from datetime import timedelta, datetime
from django.utils import timezone
import logging
from urllib.parse import urlparse

from decouple import config
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from django.http import HttpResponse, JsonResponse

# Get logger for this module specifically
logger = logging.getLogger('news.views')


def get_db_client():
    """
    Retrieves the MongoDB client connection.
    """
    try:
        logger.debug("Attempting to connect to MongoDB with URI: %s", config("MONGO_URI", default="<not-set>"))
        client = MongoClient(config("MONGO_URI"), server_api=ServerApi("1"))
        
        # Test the connection with timeout
        client.admin.command('ping', maxTimeMS=5000)
        logger.info("Successfully connected to MongoDB")
        
        # Log available databases
        databases = client.list_database_names()
        logger.debug(f"Available databases: {databases}")
        
        return client
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}", exc_info=True)
        return None


def get_website_from_link(link):
    """Extract website name from link."""
    try:
        parsed = urlparse(link)
        # Remove www. and .cl/.com
        domain = parsed.netloc.replace('www.', '').split('.')[0]
        return domain
    except:
        return 'default'


def get_news(sentiment=None, limit=None):
    """
    Retrieve news articles from the database based on the specified sentiment and limit.
    """
    client = None
    try:
        logger.debug(f"Starting get_news with sentiment={sentiment}, limit={limit}")
        
        # Check cache first
        cache_key = f"news_{sentiment}_{limit}"
        cached_news = cache.get(cache_key)
        if cached_news is not None:
            logger.info(f"Retrieved {len(cached_news)} items from cache for {cache_key}")
            return cached_news

        client = get_db_client()
        if not client:
            logger.error("Failed to get database client")
            return []

        db = client["opencoredatabase"]
        collection = db["news_news"]

        # Build query based only on sentiment and valid image URLs
        query = {
            "img_url": {
                "$exists": True,
                "$ne": "",
                "$ne": None,
                "$regex": "^https?://"  # Ensure URL starts with http:// or https://
            }
        }
        if sentiment:
            query["sentiment"] = sentiment

        # Only retrieve necessary fields
        projection = {
            "title": 1,
            "date_published": 1,
            "link": 1,
            "img_url": 1,
            "website": 1,
            "sentiment": 1,
            "_id": 0
        }

        # Use limit and batch size for better memory management
        cursor = collection.find(
            query, 
            projection
        ).sort("date_published", -1).batch_size(100)
        
        if limit:
            cursor = cursor.limit(limit)

        # Convert cursor to list with memory consideration
        news_list = []
        count = 0
        max_items = limit if limit else 1000  # Set a reasonable maximum
        
        for doc in cursor:
            if count >= max_items:
                break
                
            # Additional validation of image URL
            img_url = doc.get('img_url', '')
            if not img_url or not img_url.startswith(('http://', 'https://')):
                continue
                
            # Process website if needed
            if not doc.get('website') and doc.get('link'):
                doc['website'] = get_website_from_link(doc['link'])
                
            news_list.append(doc)
            count += 1

        logger.info(f"Retrieved {len(news_list)} documents from database")

        # Cache results if we have any
        if news_list:
            cache.set(cache_key, news_list, 3600)
            logger.info(f"Cached {len(news_list)} items")

        return news_list

    except Exception as e:
        logger.error(f"Error in get_news: {str(e)}", exc_info=True)
        return []
    finally:
        if client:
            client.close()


@cache_page(60 * 15)
def home(request):
    """
    Renders the home page with news data.
    """
    logger.info("Starting home view request")
    
    try:
        # Get latest news with a small limit
        latest_news = get_news(limit=5)
        logger.info(f"Latest news count: {len(latest_news)}")
        
        if not latest_news:
            logger.warning("No latest news available")
            return render(request, "index.html", {
                "error_message": "No news articles available at this time.",
                "latest_news": [],
                "recent_news": [],
                "neutral_news": [],
                "negative_news": [],
                "positive_news": [],
                "total_news": 0,
                "total_words": 0,
            })

        # Get other sections with reasonable limits
        recent_news = get_news(limit=20)
        logger.info(f"Recent news count: {len(recent_news)}")
        recent_news = recent_news[5:] if len(recent_news) > 5 else []
        
        # Add neutral news section
        neutral_news = get_news(sentiment="Neutro", limit=10)
        logger.info(f"Neutral news count: {len(neutral_news) if neutral_news else 0}")
        
        negative_news = get_news(sentiment="Negativo", limit=10)
        logger.info(f"Negative news count: {len(negative_news) if negative_news else 0}")
        
        positive_news = get_news(sentiment="Positivo", limit=10)
        logger.info(f"Positive news count: {len(positive_news) if positive_news else 0}")

        # Get totals more efficiently
        client = get_db_client()
        total_news = 0
        total_words = 0
        
        if client:
            try:
                db = client["opencoredatabase"]
                collection = db["news_news"]
                total_news = collection.count_documents({})
                
                # Estimate total words from a sample
                word_sample = collection.aggregate([
                    {"$sample": {"size": 100}},
                    {"$project": {"word_count": {"$size": {"$split": ["$content", " "]}}}},
                    {"$group": {"_id": None, "avg_words": {"$avg": "$word_count"}}}
                ])
                
                word_sample = list(word_sample)
                if word_sample:
                    avg_words = word_sample[0]["avg_words"]
                    total_words = int(avg_words * total_news)
                
                logger.info(f"Totals calculated: {total_news} news, {total_words} words (estimated)")
            except Exception as e:
                logger.error(f"Error calculating totals: {str(e)}")
                total_news = len(latest_news)
            finally:
                client.close()

        context = {
            "latest_news": latest_news,
            "recent_news": recent_news,
            "neutral_news": neutral_news,
            "negative_news": negative_news,
            "positive_news": positive_news,
            "total_news": total_news,
            "total_words": total_words,
        }
        
        logger.info("Rendering home page with complete context")
        return render(request, "index.html", context)

    except Exception as e:
        logger.error(f"Error in home view: {str(e)}", exc_info=True)
        return render(request, "index.html", {
            "error_message": "Unable to load news at this time. Please try again later.",
            "latest_news": [],
            "recent_news": [],
            "neutral_news": [],
            "negative_news": [],
            "positive_news": [],
            "total_news": 0,
            "total_words": 0,
        })


def sort_results(request, search_results):
    """
    Sorts the search results based on the specified sort option.

    Args:
        request (HttpRequest): The HTTP request object.
        search_results (list): The list of search results.

    Returns:
        list: The sorted search results.
    """
    sort_option = request.GET.get("sort", "relevance")

    if sort_option in ["newest", "oldest"]:
        reverse = sort_option == "newest"
        search_results.sort(key=lambda doc: doc["date_published"], reverse=reverse)

    return search_results


def search(request):
    """
    Perform a search based on the provided query, sentiments, and sources.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered search results page.

    Raises:
        None
    """
    client = get_db_client()
    db = client["opencoredatabase"]
    collection = db["news_news"]
    try:
        now = datetime.now()
        two_weeks_ago = now - timedelta(days=14)

        search_query = request.GET.get("query")
        sentiments = request.GET.getlist("sentiment")
        sources = request.GET.getlist("source")

        cache_key = (
            "search_results_"
            + "".join(e for e in search_query if e.isalnum())
            + "_sentiments_"
            + "_".join(sentiments)
            + "_sources_"
            + "_".join(sources)
        )
        results = cache.get(cache_key)
        if results is None:
            pipeline = [
                {
                    "$search": {
                        "index": "news_index",
                        "text": {"query": search_query, "path": {"wildcard": "*"}},
                    }
                },
                {
                    "$match": {
                        "date_published": {"$gte": two_weeks_ago},
                    }
                },
            ]
            if sentiments:
                pipeline.append(
                    {
                        "$match": {
                            "sentiment": {"$in": sentiments},
                        }
                    }
                )
            if sources:
                pipeline.append(
                    {
                        "$match": {
                            "website": {"$in": sources},
                        }
                    }
                )
            results = collection.aggregate(pipeline)
            results = list(results)
            cache.set(cache_key, results, 60 * 15)

        results = sort_results(request, results)
        total_results = len(results)

        page_number = request.GET.get("page", 1)
        paginator = Paginator(results, 25)

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        context = {
            "page_obj": page_obj,
            "total_results": total_results,
            "query": search_query,
            "sources": request.GET.getlist("source"),
            "sentiment": request.GET.getlist("sentiment"),
            "sort": request.GET.get("sort", "relevance"),
        }

        return render(request, "results.html", context)
    finally:
        client.close()


def stats(request):
    return render(request, "stats.html")


def test_logging(request):
    """Test view to verify logging is working."""
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    return HttpResponse("Logging test complete")


def test_db(request):
    """Test view to verify database connectivity."""
    try:
        client = get_db_client()
        if not client:
            return JsonResponse({"status": "error", "message": "Could not connect to database"})
            
        db = client["opencoredatabase"]
        collection = db["news_news"]
        
        # Get basic stats
        doc_count = collection.count_documents({})
        sample_doc = collection.find_one()
        
        return JsonResponse({
            "status": "success",
            "document_count": doc_count,
            "sample_document": str(sample_doc) if sample_doc else None,
            "databases": client.list_database_names()
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        })
    finally:
        if client:
            client.close()
