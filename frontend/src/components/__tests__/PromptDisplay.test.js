import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PromptDisplay from '../PromptDisplay';
import { ThemeProvider } from '../../contexts/ThemeContext';

// Mock environment variables
process.env.REACT_APP_API_URL = 'http://localhost:4000';

// Wrapper component for testing with theme
const renderWithTheme = (component, isDarkMode = false) => {
  // Set initial theme in localStorage before rendering
  if (isDarkMode) {
    localStorage.setItem('theme', 'dark');
  } else {
    localStorage.removeItem('theme');
  }

  return render(
    <ThemeProvider>
      {component}
    </ThemeProvider>
  );
};

describe('PromptDisplay Component', () => {
  const mockPrompt = {
    title: 'Idea Generation Drills',
    content: '**Exercise**: Write a compelling opening line for a fantasy story.\n\nFocus on creating immediate intrigue.',
    difficulty: 'Easy',
    wordCount: 500,
    tips: [
      'Start with action or dialogue',
      'Establish the world quickly',
      'Create questions in the reader\'s mind'
    ]
  };

  const mockGenres = ['Fantasy', 'Science Fiction'];

  beforeEach(() => {
    fetch.mockClear();
  });

  describe('Rendering', () => {
    test('renders prompt title and content', () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      expect(screen.getByText('Idea Generation Drills')).toBeInTheDocument();
      expect(screen.getByText(/Write a compelling opening line/)).toBeInTheDocument();
    });

    test('renders genre badges', () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      expect(screen.getByText('Fantasy')).toBeInTheDocument();
      expect(screen.getByText('Science Fiction')).toBeInTheDocument();
    });

    test('renders difficulty and word count', () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      expect(screen.getByText('Easy')).toBeInTheDocument();
      expect(screen.getByText('500 words')).toBeInTheDocument();
    });

    test('renders tips section', () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      expect(screen.getByText(/Start with action or dialogue/)).toBeInTheDocument();
      expect(screen.getByText(/Establish the world quickly/)).toBeInTheDocument();
    });

    test('renders in dark mode with correct classes', () => {
      const { container } = renderWithTheme(
        <PromptDisplay prompt={mockPrompt} genres={mockGenres} />,
        true
      );

      const mainDiv = container.firstChild;
      expect(mainDiv).toHaveClass('bg-gray-800');
    });
  });

  describe('Word Counter', () => {
    test('displays zero words initially', () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      expect(screen.getByText('0')).toBeInTheDocument();
      expect(screen.getByText('/ 500 words')).toBeInTheDocument();
    });

    test('updates word count as user types', async () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      await userEvent.type(textarea, 'The dragon soared above the mountains');

      // Should show 6 words
      await waitFor(() => {
        expect(screen.getByText('6')).toBeInTheDocument();
      });
    });

    test('counts words correctly with multiple spaces', async () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      await userEvent.type(textarea, 'Word1    Word2     Word3');

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument();
      });
    });

    test('shows target reached message when word count met', async () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      await waitFor(() => {
        expect(screen.getByText('✓ Target reached!')).toBeInTheDocument();
      });
    });

    test('displays character count', async () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      await userEvent.type(textarea, 'Test');

      await waitFor(() => {
        expect(screen.getByText('Characters: 4')).toBeInTheDocument();
      });
    });
  });

  describe('Text Download', () => {
    test('download button appears when text is entered', async () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      await userEvent.type(textarea, 'Some writing');

      await waitFor(() => {
        expect(screen.getByText('💾 Download')).toBeInTheDocument();
      });
    });

    test('download button creates blob and triggers download', async () => {
      // Mock URL.createObjectURL
      const mockCreateObjectURL = jest.fn(() => 'blob:mock-url');
      global.URL.createObjectURL = mockCreateObjectURL;

      // Mock createElement and click
      const mockClick = jest.fn();
      const mockAppendChild = jest.fn();
      const mockRemoveChild = jest.fn();
      document.body.appendChild = mockAppendChild;
      document.body.removeChild = mockRemoveChild;

      const originalCreateElement = document.createElement.bind(document);
      document.createElement = jest.fn((tag) => {
        const element = originalCreateElement(tag);
        if (tag === 'a') {
          element.click = mockClick;
        }
        return element;
      });

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      await userEvent.type(textarea, 'Test content');

      const downloadBtn = await screen.findByText('💾 Download');
      fireEvent.click(downloadBtn);

      expect(mockCreateObjectURL).toHaveBeenCalled();
      expect(mockClick).toHaveBeenCalled();
    });
  });

  describe('Clear Text', () => {
    test('clear button appears when text is entered', async () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      await userEvent.type(textarea, 'Some writing');

      await waitFor(() => {
        expect(screen.getByText('🗑️ Clear')).toBeInTheDocument();
      });
    });

    test('clear button shows confirmation dialog', async () => {
      global.confirm = jest.fn(() => false);

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      await userEvent.type(textarea, 'Some writing');

      const clearBtn = await screen.findByText('🗑️ Clear');
      fireEvent.click(clearBtn);

      expect(global.confirm).toHaveBeenCalledWith('Are you sure you want to clear all your writing?');
    });

    test('clears text when user confirms', async () => {
      global.confirm = jest.fn(() => true);

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      await userEvent.type(textarea, 'Some writing');

      const clearBtn = await screen.findByText('🗑️ Clear');
      fireEvent.click(clearBtn);

      await waitFor(() => {
        expect(textarea.value).toBe('');
      });
    });
  });

  describe('AI Feedback Submission', () => {
    test('submit button is disabled when word count not reached', () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const submitBtn = screen.getByText('📝 Submit for AI Feedback');
      expect(submitBtn).toBeDisabled();
    });

    test('shows message about word count requirement', () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      expect(screen.getByText('Complete at least 500 words to submit')).toBeInTheDocument();
    });

    test('submit button is enabled when word count reached', async () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      await waitFor(() => {
        const submitBtn = screen.getByText('📝 Submit for AI Feedback');
        expect(submitBtn).not.toBeDisabled();
      });
    });

    test('submits feedback request with correct data', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feedback: '### Strengths\n\nGood work!' })
      });

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      const submitBtn = await screen.findByText('📝 Submit for AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          'http://localhost:4000/api/writing/feedback',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: expect.stringContaining('"exercise"')
          })
        );
      });

      const call = fetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.exerciseType).toBe('Idea Generation Drills');
      expect(body.genres).toEqual(['Fantasy', 'Science Fiction']);
      expect(body.difficulty).toBe('Easy');
      expect(body.wordCount).toBe(500);
    });

    test('shows loading state during feedback request', async () => {
      fetch.mockImplementationOnce(() => new Promise(() => {})); // Never resolves

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      const submitBtn = await screen.findByText('📝 Submit for AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText('Getting Feedback...')).toBeInTheDocument();
      });
    });

    test('displays feedback after successful request', async () => {
      const mockFeedback = '### Strengths\n\nYour opening is engaging.\n\n### Areas for Improvement\n\nConsider adding more sensory details.';

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feedback: mockFeedback })
      });

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      const submitBtn = await screen.findByText('📝 Submit for AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText('✨ AI Feedback')).toBeInTheDocument();
        expect(screen.getByText('Strengths')).toBeInTheDocument();
        expect(screen.getByText(/Your opening is engaging/)).toBeInTheDocument();
      });
    });

    test('displays error message on failed request', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 500
      });

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      const submitBtn = await screen.findByText('📝 Submit for AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Error getting feedback/)).toBeInTheDocument();
      });
    });
  });

  describe('Markdown Rendering', () => {
    test('renders bold text in prompt content', () => {
      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const boldElement = screen.getByText('Exercise');
      expect(boldElement.tagName).toBe('STRONG');
    });

    test('renders H3 headings in feedback', async () => {
      const mockFeedback = '### Strengths\n\nGood work!';

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feedback: mockFeedback })
      });

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      const submitBtn = await screen.findByText('📝 Submit for AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        const heading = screen.getByText('Strengths');
        expect(heading.tagName).toBe('H3');
      });
    });

    test('renders bullet lists in feedback', async () => {
      const mockFeedback = '- Point one\n- Point two\n- Point three';

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feedback: mockFeedback })
      });

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      const submitBtn = await screen.findByText('📝 Submit for AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Point one/)).toBeInTheDocument();
        expect(screen.getByText(/Point two/)).toBeInTheDocument();
        expect(screen.getByText(/Point three/)).toBeInTheDocument();
      });
    });
  });

  describe('XSS Prevention', () => {
    test('sanitizes malicious script tags in feedback', async () => {
      const maliciousFeedback = '<script>alert("XSS")</script>Good feedback here';

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feedback: maliciousFeedback })
      });

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      const submitBtn = await screen.findByText('📝 Submit for AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        // Script tags should not be executed, only text content shown
        const container = screen.getByText(/Good feedback here/);
        expect(container).toBeInTheDocument();
        expect(document.querySelector('script')).toBeNull();
      });
    });

    test('does not execute javascript: URLs in markdown', async () => {
      const maliciousFeedback = '[Click me](javascript:alert("XSS"))';

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feedback: maliciousFeedback })
      });

      renderWithTheme(<PromptDisplay prompt={mockPrompt} genres={mockGenres} />);

      const textarea = screen.getByPlaceholderText(/Start writing here/);
      const longText = Array(500).fill('word').join(' ');
      await userEvent.type(textarea, longText);

      const submitBtn = await screen.findByText('📝 Submit for AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        // Should render as text, not as a clickable link
        expect(screen.getByText(/Click me/)).toBeInTheDocument();
      });
    });
  });
});
