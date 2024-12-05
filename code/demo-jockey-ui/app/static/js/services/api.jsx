// api.jsx
import { Client } from "@langchain/langgraph-sdk";

const jockeyClient = new Client({apiUrl: "https://spooky.jockey.ngrok.app"});

export const processText = async (text, indexId, threadId) => {
    const url = '/api/process';
    console.log("Request URL:", url);
    
    // Format matches what we see in the successful response
    const formattedBody = {
        text: text,
        thread_id: threadId,
        index_id: indexId,
        additional_kwargs: {
            index_id: indexId,
            example: false
        }
    };
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formattedBody),
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
};
export const initializeThread = async () => {
    const response = await fetch('/api/process/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
    });
    
    if (!response.ok) {
        throw new Error(`Thread initialization failed: ${response.status}`);
    }
    
    return response.json();
};