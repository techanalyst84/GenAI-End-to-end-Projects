from crewai import Agent
from dotenv import load_dotenv
import os
import langchain_google_genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders import YoutubeLoader
from googleapiclient.discovery import build  # For interacting with the YouTube API
from fpdf import FPDF  # Library for creating PDF files
from crewai import Agent, Task, Crew, Process
from crewai_tools import PDFSearchTool  # Import the PDF search tool
from dotenv import load_dotenv


load_dotenv()

# Setup LLM with Google Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    verbose=True,
    temperature=0.5,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)
# Function to retrieve the actual channel ID from the YouTube handle
def get_channel_id_from_handle(handle):
    YOUTUBE_API_KEY=os.getenv("YOUTUBE_API_KEY")
    api_key = YOUTUBE_API_KEY  # Ensure your API key is set in the environment
    youtube = build('youtube', 'v3', developerKey=api_key)

    # Retrieve channel ID from the handle
    response = youtube.search().list(
         part="snippet",
        q=handle,  # Pass the handle (e.g., @channelName)
        type="channel",  # Limit search to channels
        maxResults=1

).execute()

    if response['items']:
        return response["items"][0]["id"]["channelId"]
    else:
        raise ValueError(f"No channel found for handle: {handle}")

# Function to retrieve video URLs from a YouTube channel using channel ID
def get_channel_video_urls(channel_id):
    api_key = os.getenv("YOUTUBE_API_KEY")
    youtube = build('youtube', 'v3', developerKey=api_key)

    video_urls = []
    next_page_token = None
 
    search_request = youtube.search().list(
            part='snippet',
            channelId=channel_id,
            maxResults=50,
            order='date',
            type='video',
            pageToken=next_page_token
        ) 
    search_response=search_request.execute()

    for item in search_response['items']:
            video_id = item['id']['videoId']
            video_urls.append(f"https://www.youtube.com/watch?v={video_id}")

    next_page_token = search_response.get('nextPageToken')

    return video_urls

# Function to fetch YouTube transcripts using YoutubeLoader
def fetch_video_transcripts(video_url):
    try:
        loader = YoutubeLoader.from_youtube_url(video_url)
        docs = loader.load()
        return docs[0].page_content
    except Exception as e:
        return None

# Custom tool to fetch transcripts for all videos in a YouTube channel
def yt_tool(channel_handle):
    try:
        # Get the actual channel ID using the handle
        channel_id = get_channel_id_from_handle(channel_handle)
    except ValueError as e:
        return str(e)

    video_urls = get_channel_video_urls(channel_id)
    if not video_urls:
        return "No videos found for this channel."

    transcripts = {}
    for video_url in video_urls:
        transcript = fetch_video_transcripts(video_url)
        transcripts[video_url] = transcript if transcript else "Transcript not available."

    return transcripts

# Function to write transcripts to a PDF file
def write_transcripts_to_pdf(transcripts, output_filename):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for video_url, transcript in transcripts.items():
        pdf.cell(200, 10, txt=f"Video URL: {video_url}", ln=True)
        pdf.multi_cell(0, 10, txt=transcript)
        pdf.ln(10)

    # Save the PDF to the specified file
    pdf.output(output_filename)

# Main execution
youtube_channel_handle = "@rajasdataengineering7585"
#"@krishnaik06" 
 # Replace with the actual channel handle
yt_tool_instance = yt_tool(youtube_channel_handle)

# Save the transcripts to a PDF
output_pdf_file = "youtube_channel_"+youtube_channel_handle.replace('@', '')+"transcripts.pdf"
write_transcripts_to_pdf(yt_tool_instance, output_pdf_file)


output_pdf_file = "youtube_channel_"+youtube_channel_handle.replace('@', '')+"transcripts.pdf"


# Set your API key and model name
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_MODEL_NAME"] = "gpt-4-0125-preview"

 

# Initialize the PDFSearchTool
pdf_tool = PDFSearchTool(pdf=output_pdf_file)

# Create a senior blog content researcher for PDFs
blog_researcher = Agent(
    role='Blog Researcher from PDF Documents',
    goal='Extract relevant information on the topic {topic} from the provided PDF documents.',
    verbose=True,
    memory=True,
    backstory=(
        "Expert in analyzing PDF content and providing insights and summaries."
    ),
    tools=[pdf_tool],
    allow_delegation=True
)

# Create a senior blog writer agent for PDFs
blog_writer = Agent(
    role='Blog Writer',
    goal='Narrate compelling tech stories based on the extracted information for the topic {topic}.',
    verbose=True,
    memory=True,
    backstory=(
        "With a flair for simplifying complex topics, you craft"
        "engaging narratives that captivate and educate, bringing new"
        "discoveries to light in an accessible manner."
    ),
    tools=[pdf_tool],
    allow_delegation=False
)

# Research Task
research_task = Task(
    description=(
        "Identify and extract information relevant to the topic {topic} from the provided PDF document."
    ),
    expected_output='A comprehensive 3-paragraph report based on the {topic} extracted from the PDF content.',
    tools=[pdf_tool],
    agent=blog_researcher,
)

# Writing task with language model configuration
write_task = Task(
    description=(
        "Summarize the extracted information from the PDF document regarding the topic {topic} and create the content for the blog."
    ),
    expected_output='A well-structured blog post based on the information extracted from the PDF on the topic {topic}.',
    tools=[pdf_tool],
    agent=blog_writer,
    async_execution=False,
    output_file='new-blog-post.md'  # Example of output customization
)

# Forming the tech-focused crew with some enhanced configurations
crew = Crew(
    agents=[blog_researcher, blog_writer],
    tasks=[research_task, write_task],
    process=Process.sequential,  # Sequential task execution
    memory=True,
    cache=True,
    max_rpm=100,
    share_crew=True
)

# Kick off the crew with a topic input
result = crew.kickoff(inputs={'topic': 'what is difference between Spark and hive'})