import pandas as pd
import streamlit as st
from streamlit_lottie import st_lottie
import pickle
import threading
import openai
import requests
import bs4
import tiktoken
from openai.embeddings_utils import get_embedding, cosine_similarity

tokenizer = tiktoken.get_encoding("gpt2")


def google_search(search: str, search_depth: int):
    try:
        res = requests.get('https://google.com/search?q=' + search)
        res.raise_for_status() # Raise if a HTTPError occured
    except:
        st.warning("There was a problem with your internet.😵  \nIf you got HTTPError: 429, that means your IP is being rate limited by Google. If you are using a VPN try disabling it. Alternatively, you can try searching again another day.😢")
        raise

    soup = bs4.BeautifulSoup(res.text, 'html.parser')

    link_elements = soup.select('a')
    links = [link.get('href').split('&sa=U&ved=')[0].replace('/url?q=', '')
             for link in link_elements
             if '/url?q=' in link.get('href') and
             'accounts.google.com' not in link.get('href') and
             'support.google.com' not in link.get('href')]
    links = list(set(links)) # Remove duplicates while mainaining the same order
    google_text = soup.get_text(separator='\n')
    
    links_attempted = -1
    links_explored = 0
    google_results = pd.DataFrame(columns=['text', 'link', 'query'])
    
    link_history = st.session_state['google_history']['link'].unique().tolist()
    while links_explored < search_depth or links_attempted == len(links):
        links_attempted += 1
        if links[links_attempted] in link_history: continue
        # If this link does not work, go to the next one
        try:
            res = requests.get(links[links_attempted])
            res.raise_for_status()
        except:
            continue
        
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        _link_text = list(set(soup.get_text(separator='\n'))) # Separate all text by lines and remove duplicates
        _useful_text = [s for s in _link_text if len(s) > 30] # Get only strings above 30 characters
        _links = [links[links_attempted] for i in range(len(_useful_text))]
        _query = [search for i in range(len(_useful_text))]
        print('-----------------------')
        print(soup.get_text(separator='\n'))
        print('-----------------------')
        _link_results = pd.DataFrame({'text': _useful_text, 'link': _links, 'query': _query})
        google_results = pd.concat([google_results, _link_results])
        links_explored += 1
    
    google_results = google_results.drop_duplicates()
    #google_results['ada_search'] = google_results['text'].apply(lambda x: get_embedding(x, engine='text-embedding-ada-002'))
    
    return google_results
        
    
    # Here I'm predicting where the useful information in the string is. Since some have reported different formatting, it is in a try block.
    #try:
    #    google_text = google_text.split('All results\nAll results\nVerbatim\n')[1]
    #except:
    #    pass
    #try:
    #    google_text = google_text.split('Next >')[0]
    #except:
    #    pass

    #return google_text, links


@st.cache
def find_top_similar_results(df: pd.DataFrame, query: str, n: int):
    embedding = get_embedding(query, engine="text-embedding-ada-002")
    df1 = df.copy()
    df1["similarities"] = df1["ada_search"].apply(lambda x: cosine_similarity(x, embedding))
    return df1.sort_values("similarities", ascending=False).head(n)

@st.cache
def gpt3_call(prompt: str, tokens: int, temperature: int=1, stop=None):
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=tokens,
        n=1,
        stop=stop,
        temperature=temperature)

    return response["choices"][0]["text"].replace('\n', '  \n')


@st.cache
def load_lottie_url(url: str):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

def markdown_litteral(string: str):
    return string.replace('$','\$')

def num_of_tokens(prompt: str):
    return len(tokenizer.encode(prompt))

def load_google_history():
    # Try to find the search_history, if can't find it, create a new search_history
    try:
        with open('search_history.pickle', 'rb') as f:
            return pickle.load(f)
    except:
        data = pd.DataFrame(columns=['text', 'link', 'query'])
        with open('search_history.pickle', 'wb') as f:
            pickle.dump(data, f)
        return data

def save_google_history(data):
    with open('search_history.pickle', 'wb') as f:
        pickle.dump(data, f)
        
def save_google_history_in_thread(data):
    thread = threading.Thread(target=save_google_history, args=(data))
    thread.start()

st.set_page_config(page_title='Quest🔍')
st.title("Quest🔍")
st.markdown("By [Rafael Moraes](https://github.com/farrael004)")
st.markdown('---')

# Setting how factual/creative the model will be. This can be tunned.
assistant_settings = st.sidebar.selectbox('Assistant settings',
                                          ['Strictly Factual', 'Factual', 'Neutral', 'Creative', 'Very Creative'],
                                          help='Determines how close to the facts already presented the Assistent will be.',
                                          index=2)

match assistant_settings:
    case 'Strictly Factual':
        warn_assistant = "\nWARNING: If the user asks for information that is not in their google search, try to answer the question as factualy as possible and warn the user about this absence. DO NOT provide any hyperlinks.\n"
        starting_conversation = ['User: Who are you?',
                                 'Assistant: Hello, my name is Assistant. How can I help you?',
                                 'User: How much is the toy car from my search?',
                                 "Assistant: Unfortunately your Google search did not specify prices for gifts, but based on your search, I do have some information about popular gifts for kids in 2022.",
                                 "User: Can you show me how to loop between 0 and 9 in python?",
                                 "Assistant: Sure. Here's how you can loop between 0 and 9 in python:\n```python\nfor i in range(10):\n    print(i)\n```"]

    case 'Factual':
        warn_assistant = "\nWARNING: If the user asks for information that is not in their google search, try to answer the question but warn about potential lack of precise or up to date information. DO NOT provide any hyperlinks.\n"
        starting_conversation = ['User: Who are you?',
                                 'Assistant: Hello, my name is Assistant. How can I help you?',
                                 'User: How much is the toy car from my search?',
                                 "Assistant: Unfortunately your Google search did not specify prices for gifts, but I do have some information about popular gifts for kids in 2022.",
                                 "User: Can you show me how to loop between 0 and 9 in python?",
                                 "Assistant: Sure. Here's how you can loop between 0 and 9 in python:\n```python\nfor i in range(10):\n    print(i)\n```"]
    case 'Neutral':
        warn_assistant = "\nATTENTION: If the user asks for information that is not in their google search, try to answer the question to the best of your knowledge but warn about potential lack of precise or up to date information.\n"
        starting_conversation = ['User: Who are you?',
                                 'Assistant: Hello, my name is Assistant. How can I help you?',
                                 'User: How much is the toy car from my search?',
                                 "Assistant: Unfortunately your Google search did not specify prices for gifts, but I do have some information about popular gifts for kids in 2022.",
                                 "User: Can you show me how to loop between 0 and 9 in python?",
                                 "Assistant: Sure. Here's how you can loop between 0 and 9 in python:\n```python\nfor i in range(10):\n    print(i)\n```"]
    case 'Creative':
        warn_assistant = "\nATTENTION: If the user asks for information that is not in their google search, try to answer the question in a way that seems correct but warn about potential lack of precise or up to date information.\n"
        starting_conversation = ['User: Who are you?',
                                 'Assistant: Hello, my name is Assistant. How can I help you?',
                                 'User: How much is the toy car from my search?',
                                 "Assistant: Unfortunately your Google search did not specify prices for gifts, but I do have some information about popular gifts for kids in 2022.",
                                 "User: Can you show me how to loop between 0 and 9 in python?",
                                 "Assistant: Sure. Here's how you can loop between 0 and 9 in python:\n```python\nfor i in range(10):\n    print(i)\n```"]
    case 'Very Creative':
        warn_assistant = ''
        starting_conversation = ['User: Who are you?',
                                 'Assistant: Hello, my name is Assistant. How can I help you?',
                                 "User: Can you show me how to loop between 0 and 9 in python?",
                                 "Assistant: Sure. Here's how you can loop between 0 and 9 in python:\n```python\nfor i in range(10):\n    print(i)\n```"]

with st.sidebar:
    lottie_image1 = load_lottie_url('https://assets10.lottiefiles.com/packages/lf20_ofa3xwo7.json')
    st_lottie(lottie_image1)

# Load the API key
if 'api_key' not in st.session_state:
    try:
        with open('api_key.txt') as api_key:
            st.session_state['api_key'] = api_key.read()
    except:
        with st.form('API Key'):
            api_key = st.text_input(label='Insert your API key here')
            api_submitted = st.form_submit_button("Submit")
            api_checkbox = st.checkbox('Save my key')
            st.markdown("NOTE: By saving your key, it will be stored in a local file without encryption.")

        st.markdown("[Find your API key here](https://beta.openai.com/account/api-keys)")
        
        if api_submitted and api_checkbox:
            f = open("api_key.txt", "a")
            f.write(api_key)
            f.close()
            
        if api_submitted:
            st.session_state['api_key'] = api_key
            st.experimental_rerun()
        
        st.stop()
  
openai.api_key = st.session_state['api_key']

# App layout
response = st.container()
chat = st.container()
search = st.expander('Google Search', expanded=True)

# Defining google search history
if 'google_history' not in st.session_state:
    st.session_state['google_history'] = load_google_history()

if 'google_findings' not in st.session_state:
    st.session_state['google_findings'] = []
if 'links' not in st.session_state:
    st.session_state['links'] = []
if 'user_queries' not in st.session_state:
    st.session_state['user_queries'] = []

google_findings = st.session_state['google_findings']
links = st.session_state['links']
user_queries = st.session_state['user_queries']

# Google search section
with search:
    with st.form('Google'):
        user_query_text = st.text_input(label='')
        google_submitted = st.form_submit_button("Submit")
        
        query_history = st.session_state['google_history']['query'].unique().tolist()
        if google_submitted and user_query_text != '' and user_query_text not in query_history:
            search_results = google_search(user_query_text, 3)
            st.session_state['google_history'] = pd.concat([st.session_state['google_history'], search_results]).drop_duplicates()
            save_google_history(st.session_state['google_history'])
            #similar_results = find_top_similar_results(search_results, user_query_text, 6)
            
            #google_findings = st.session_state['google_findings'].append(similar_results['text'].to_list())
            #links = st.session_state['links'].append(similar_results['link'].to_list())
            #user_queries = st.session_state['user_queries'].append(user_query_text)
            
        if google_submitted and user_query_text in query_history:
            st.warning("This query is cached in your history already")
            
    #if len(google_findings) > 0:
        # Iterate backwards so older searches are at the bottom
        #for i in range(len(google_findings) - 1, -1, -1):
            #st.markdown('---')
            #st.markdown(f'# {user_queries[i]}')
            #for finding in google_findings[i]:
            #    st.markdown(markdown_litteral(finding))

            #st.markdown('---')
            #st.write('Sources:')
            #for link in links[i]:
            #    st.write(link)

# Section where user inputs directly to GPT
with chat:
    with st.form('Chat'):
        user_chat_text = st.text_input(label="Ask me anything")
        chat_submitted = st.form_submit_button("Submit")

# Initialize the conversation if it was not initialized before or if the assistant settings changed
if 'conversation' not in st.session_state or starting_conversation != st.session_state['conversation'][:len(starting_conversation)]:
    st.session_state['conversation'] = starting_conversation

with response:
    # Show conversation so far
    chat_so_far = ''
    for i, text in enumerate(st.session_state['conversation']):
        chat_so_far += text + '\n'
        if i < len(starting_conversation): continue
        if text[:4] == 'User':
            text = '👤' + text
        else:
            text = '🖥️' + markdown_litteral(text)
        st.write(text)
        st.markdown('---')

    # Submits new prompt
    if chat_submitted:
        st.write('👤User: ' + user_chat_text)
        st.session_state['conversation'].append('User: ' + user_chat_text)

        prompt = 'You are a friendly and helpful AI assistant. You have access to the internet if the user makes a google search.\n'
        if google_findings[-1] != '':
            prompt += "The user asked you to google search:\n" + user_queries[-1] + "\nYour findings are:" + \
                      google_findings[-1] + "\n"
        else:
            prompt += "The user did not make a google search to provide more information.\n"
        prompt += 'This is the conversation so far:\n' + chat_so_far + 'User: ' + user_chat_text + warn_assistant + '\nAssistant:'

        tokens = num_of_tokens(prompt)
        answer = gpt3_call(prompt, tokens=4000 - tokens, stop='User:')
        st.session_state['conversation'].append('Assistant: ' + answer)
        print(prompt + answer)
        st.markdown('---')
        st.write('🖥️Assistant: ' + answer)
