import streamlit as st
import os
import PyPDF2
import requests
import json
from pathlib import Path

# Set up page configuration
st.set_page_config(page_title="E-Library Organizer", layout="wide")

# API key for Google Books API
GOOGLE_BOOKS_API_KEY = st.secrets["GOOGLE_BOOKS_API_KEY"]

# Create directories for storing files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Session state initialization
if 'library' not in st.session_state:
    st.session_state.library = []

def extract_pdf_metadata(file_path):
    """Extract metadata and content from PDF files"""
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            info = reader.metadata
            
            # Extract text from first page for better title/content detection
            first_page_text = reader.pages[0].extract_text() if len(reader.pages) > 0 else ""
            
            # Try to determine if it's a resume/CV
            is_resume = any(keyword in first_page_text.lower() for keyword in 
                           ['resume', 'cv', 'curriculum vitae', 'professional experience', 
                            'education', 'skills', 'work experience'])
            
            title = info.title if info.title else Path(file_path).stem
            author = info.author if info.author else "Unknown"
            
            # For resumes/CVs, try to extract the person's name from first few lines
            if is_resume:
                lines = first_page_text.split('\n')
                # Usually the name is in the first 3 lines and has 2+ words
                for line in lines[:3]:
                    if len(line.split()) >= 2 and not any(char.isdigit() for char in line):
                        author = line.strip()
                        break
                
                return {
                    'title': "Resume/CV" if title == Path(file_path).stem else title,
                    'author': author,
                    'pages': len(reader.pages),
                    'is_resume': True,
                    'content_preview': first_page_text[:500]  # Preview for better categorization
                }
            
            return {
                'title': title,
                'author': author,
                'pages': len(reader.pages),
                'is_resume': False,
                'content_preview': first_page_text[:500]
            }
    except Exception as e:
        st.error(f"Error extracting PDF metadata: {e}")
        return {
            'title': Path(file_path).stem, 
            'author': "Unknown", 
            'pages': 0,
            'is_resume': False,
            'content_preview': ""
        }

def fetch_book_info(title, author, content_preview="", is_resume=False):
    """Fetch book information from Google Books API or categorize document"""
    # For resumes/CVs, use a different categorization approach
    if is_resume:
        return {
            'title': title,
            'author': author,
            'genre': "Resume/CV",
            'description': f"Professional document for {author}. " + content_preview[:150] + "...",
            'thumbnail': "https://cdn-icons-png.flaticon.com/512/3135/3135692.png"  # Default resume icon
        }
    
    # For regular books, use Google Books API
    query = f"{title} {author}".replace(" ", "+")
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&key={GOOGLE_BOOKS_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if 'items' in data and len(data['items']) > 0:
            book_info = data['items'][0]['volumeInfo']
            return {
                'title': book_info.get('title', title),
                'author': book_info.get('authors', [author])[0],
                'genre': book_info.get('categories', ["Uncategorized"])[0],
                'description': book_info.get('description', "No description available"),
                'thumbnail': book_info.get('imageLinks', {}).get('thumbnail', None)
            }
    except Exception as e:
        st.error(f"Error fetching book info: {e}")
    
    # If Google Books API fails or doesn't have info, try to categorize based on content
    categories = {
        "Business": ["business", "management", "finance", "marketing", "economics"],
        "Technology": ["programming", "software", "computer", "technology", "engineering"],
        "Science": ["science", "physics", "chemistry", "biology", "research"],
        "Education": ["education", "learning", "teaching", "academic", "school"],
        "Other": []
    }
    
    content_lower = content_preview.lower()
    for category, keywords in categories.items():
        if any(keyword in content_lower for keyword in keywords):
            return {
                'title': title,
                'author': author,
                'genre': category,
                'description': content_preview[:200] + "...",
                'thumbnail': None
            }
    
    return {
        'title': title,
        'author': author,
        'genre': "Document",
        'description': content_preview[:200] + "...",
        'thumbnail': "https://cdn-icons-png.flaticon.com/512/337/337946.png"  # Default document icon
    }

def get_recommendations(genre, library):
    """Get book recommendations based on genre"""
    recommendations = []
    for book in library:
        if book['genre'] == genre and book not in recommendations:
            recommendations.append(book)
    return recommendations[:3]  # Return top 3 recommendations

# Main app interface
st.title("E-Library Organizer")

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Upload Books", "My Library", "Recommendations"])

if page == "Upload Books":
    st.header("Upload Books & Documents")
    
    uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'])
    
    if uploaded_file is not None:
        # Save the uploaded file
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Extract metadata
        metadata = extract_pdf_metadata(file_path)
        
        # Fetch additional info
        book_info = fetch_book_info(
            metadata['title'], 
            metadata['author'], 
            metadata.get('content_preview', ''),
            metadata.get('is_resume', False)
        )
        
        # Combine information
        book_data = {
            'file_path': file_path,
            'title': book_info['title'],
            'author': book_info['author'],
            'genre': book_info['genre'],
            'pages': metadata['pages'],
            'description': book_info['description'],
            'thumbnail': book_info['thumbnail']
        }
        
        # Display book info
        st.success(f"File uploaded: {uploaded_file.name}")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if book_data['thumbnail']:
                st.image(book_data['thumbnail'], width=150)
            else:
                st.write("No thumbnail available")
        
        with col2:
            st.subheader(book_data['title'])
            st.write(f"**Author:** {book_data['author']}")
            st.write(f"**Genre:** {book_data['genre']}")
            st.write(f"**Pages:** {book_data['pages']}")
            st.write(f"**Description:** {book_data['description'][:200]}...")
        
        # Add to library
        if st.button("Add to Library"):
            st.session_state.library.append(book_data)
            st.success("Book added to your library!")

elif page == "My Library":
    st.header("My Library")
    
    if not st.session_state.library:
        st.info("Your library is empty. Upload some books!")
    else:
        # Add search functionality
        search_query = st.text_input("Search your library", "")
        
        # Filter books based on search query
        filtered_books = st.session_state.library
        if search_query:
            filtered_books = [book for book in st.session_state.library if 
                             search_query.lower() in book['title'].lower() or 
                             search_query.lower() in book['author'].lower() or
                             search_query.lower() in book['genre'].lower()]
        
        # Add sorting options
        sort_by = st.selectbox("Sort by", ["Title", "Author", "Genre"])
        if sort_by == "Title":
            filtered_books = sorted(filtered_books, key=lambda x: x['title'])
        elif sort_by == "Author":
            filtered_books = sorted(filtered_books, key=lambda x: x['author'])
        else:
            filtered_books = sorted(filtered_books, key=lambda x: x['genre'])
        
        # Group books by genre
        genres = {}
        for book in filtered_books:
            genre = book['genre']
            if genre not in genres:
                genres[genre] = []
            genres[genre].append(book)
        
        # Display books by genre
        for genre, books in genres.items():
            st.subheader(genre)
            cols = st.columns(3)
            
            for i, book in enumerate(books):
                with cols[i % 3]:
                    if book['thumbnail']:
                        try:
                            thumbnail_url = book['thumbnail'].replace('http://', 'https://')
                            st.image(thumbnail_url, width=100)
                        except Exception:
                            st.write("📚") # Fallback book emoji if image fails
                    st.write(f"**{book['title']}**")
                    st.write(f"By {book['author']}")
                    st.write(f"{book['pages']} pages")

elif page == "Recommendations":
    st.header("Recommendations")
    
    if not st.session_state.library:
        st.info("Add books to your library to get recommendations!")
    else:
        # Get user's most common genre
        genre_count = {}
        for book in st.session_state.library:
            genre = book['genre']
            if genre in genre_count:
                genre_count[genre] += 1
            else:
                genre_count[genre] = 1
        
        favorite_genre = max(genre_count, key=genre_count.get)
        
        st.subheader(f"Based on your interest in {favorite_genre}")
        
        # Get recommendations
        recommendations = get_recommendations(favorite_genre, st.session_state.library)
        
        if recommendations:
            cols = st.columns(len(recommendations))
            for i, book in enumerate(recommendations):
                with cols[i]:
                    if book['thumbnail']:
                        try:
                            thumbnail_url = book['thumbnail'].replace('http://', 'https://')
                            st.image(thumbnail_url, width=100)
                        except Exception:
                            st.write("📚") # Fallback book emoji
                    st.write(f"**{book['title']}**")
                    st.write(f"By {book['author']}")
        else:
            st.write("No recommendations available yet.")








