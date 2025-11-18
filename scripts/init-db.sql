-- Database initialization script for Writing Prompt Generator
-- This creates all necessary tables and indexes

-- Create users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    picture TEXT,
    webhook_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create prompts table for storing generated prompts
CREATE TABLE IF NOT EXISTS prompts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(500),
    content TEXT,
    difficulty VARCHAR(50),
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create prompt_genres table for many-to-many relationship
CREATE TABLE IF NOT EXISTS prompt_genres (
    id SERIAL PRIMARY KEY,
    prompt_id INTEGER REFERENCES prompts(id) ON DELETE CASCADE,
    genre VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_prompts_user_id ON prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_prompt_genres_prompt_id ON prompt_genres(prompt_id);

-- Optional: Insert some test data (uncomment if needed)
-- INSERT INTO users (google_id, email, name) 
-- VALUES ('test_google_id', 'test@example.com', 'Test User');