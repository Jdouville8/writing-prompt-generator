import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DrawingPromptDisplay from '../DrawingPromptDisplay';
import { ThemeProvider } from '../../contexts/ThemeContext';

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

describe('DrawingPromptDisplay Component', () => {
  const mockPrompt = {
    title: 'Gesture Drawing Exercise',
    content: 'Practice capturing the energy and flow of poses in quick sketches.',
    difficulty: 'Intermediate',
    estimatedTime: '10 minutes',
    skills: ['Gesture', 'Form (3D Thinking)'],
    tips: [
      'Start with the line of action',
      'Think in 3D volumes',
      'Keep your hand moving'
    ]
  };

  beforeEach(() => {
    fetch.mockClear();
    jest.clearAllTimers();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    test('renders prompt title and metadata', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      expect(screen.getByText('Gesture Drawing Exercise')).toBeInTheDocument();
      expect(screen.getByText('Intermediate')).toBeInTheDocument();
      expect(screen.getByText('⏱ 10 minutes')).toBeInTheDocument();
    });

    test('renders skill badges', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      expect(screen.getByText('🎨 Gesture')).toBeInTheDocument();
      expect(screen.getByText('🎨 Form (3D Thinking)')).toBeInTheDocument();
    });

    test('renders exercise content', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      expect(screen.getByText(/Practice capturing the energy/)).toBeInTheDocument();
    });

    test('renders tips section', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      expect(screen.getByText(/Start with the line of action/)).toBeInTheDocument();
      expect(screen.getByText(/Think in 3D volumes/)).toBeInTheDocument();
    });
  });

  describe('Timer Functionality', () => {
    test('displays initial time correctly', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      expect(screen.getByText('10:00')).toBeInTheDocument();
    });

    test('starts timer when start button clicked', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const startBtn = screen.getByText('Start');
      fireEvent.click(startBtn);

      expect(screen.getByText('Pause')).toBeInTheDocument();

      jest.advanceTimersByTime(1000);

      expect(screen.getByText('9:59')).toBeInTheDocument();
    });

    test('pauses timer when pause button clicked', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const startBtn = screen.getByText('Start');
      fireEvent.click(startBtn);

      jest.advanceTimersByTime(5000);

      const pauseBtn = screen.getByText('Pause');
      fireEvent.click(pauseBtn);

      const currentTime = screen.getByText('9:55');
      jest.advanceTimersByTime(5000);

      // Time should not change after pause
      expect(currentTime).toBeInTheDocument();
    });

    test('resets timer when reset button clicked', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const startBtn = screen.getByText('Start');
      fireEvent.click(startBtn);

      jest.advanceTimersByTime(30000);

      const resetBtn = screen.getByText('Reset');
      fireEvent.click(resetBtn);

      expect(screen.getByText('10:00')).toBeInTheDocument();
      expect(screen.getByText('Start')).toBeInTheDocument();
    });

    test('shows time\'s up message when timer reaches zero', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const startBtn = screen.getByText('Start');
      fireEvent.click(startBtn);

      jest.advanceTimersByTime(600000); // 10 minutes

      expect(screen.getByText('⏰ Time\'s up!')).toBeInTheDocument();
    });
  });

  describe('Image Upload - Click', () => {
    test('shows upload prompt initially', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      expect(screen.getByText('Click to upload or drag and drop')).toBeInTheDocument();
      expect(screen.getByText('JPG or PNG (max 20MB)')).toBeInTheDocument();
    });

    test('accepts valid JPG file', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      // Mock FileReader
      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);

      // Trigger onloadend
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByAltText('Drawing preview')).toBeInTheDocument();
      });
    });

    test('accepts valid PNG file', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.png', { type: 'image/png' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/png;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByAltText('Drawing preview')).toBeInTheDocument();
      });
    });

    test('rejects invalid file types', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.gif', { type: 'image/gif' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      await userEvent.upload(input, file);

      await waitFor(() => {
        expect(screen.getByText(/Please upload a JPG or PNG image/)).toBeInTheDocument();
      });
    });

    test('rejects files larger than 20MB', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      // Create a file larger than 20MB
      const largeFile = new File([new ArrayBuffer(21 * 1024 * 1024)], 'large.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      await userEvent.upload(input, largeFile);

      await waitFor(() => {
        expect(screen.getByText(/Image file is too large/)).toBeInTheDocument();
        expect(screen.getByText(/smaller than 20MB/)).toBeInTheDocument();
      });
    });

    test('allows removing uploaded image', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByAltText('Drawing preview')).toBeInTheDocument();
      });

      // Find and click remove button (X button)
      const removeBtn = screen.getByRole('button', { name: '' }); // SVG X icon
      fireEvent.click(removeBtn);

      await waitFor(() => {
        expect(screen.queryByAltText('Drawing preview')).not.toBeInTheDocument();
        expect(screen.getByText('Click to upload or drag and drop')).toBeInTheDocument();
      });
    });
  });

  describe('Image Upload - Drag and Drop', () => {
    test('shows drag indicator when dragging over', () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const dropzone = screen.getByText('Click to upload or drag and drop').closest('div').parentElement;

      fireEvent.dragEnter(dropzone, {
        dataTransfer: {
          files: [new File(['dummy'], 'test.jpg', { type: 'image/jpeg' })]
        }
      });

      expect(screen.getByText('Drop your image here')).toBeInTheDocument();
    });

    test('handles file drop', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const dropzone = screen.getByText('Click to upload or drag and drop').closest('div').parentElement;

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      fireEvent.drop(dropzone, {
        dataTransfer: {
          files: [file]
        }
      });

      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByAltText('Drawing preview')).toBeInTheDocument();
      });
    });

    test('resets drag state after drop', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const dropzone = screen.getByText('Click to upload or drag and drop').closest('div').parentElement;

      fireEvent.dragEnter(dropzone);
      expect(screen.getByText('Drop your image here')).toBeInTheDocument();

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      fireEvent.drop(dropzone, {
        dataTransfer: {
          files: [file]
        }
      });

      // Drag indicator should be gone
      expect(screen.queryByText('Drop your image here')).not.toBeInTheDocument();
    });
  });

  describe('AI Feedback Submission', () => {
    test('shows submit button after image upload', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByText('🎨 Get AI Feedback')).toBeInTheDocument();
      });
    });

    test('submits image for feedback with correct data', async () => {
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feedback: '### Strengths\n\nGood gesture!' })
      });

      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      const mockBase64 = 'data:image/jpeg;base64,mockbase64data';
      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        onerror: null,
        result: mockBase64
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByText('🎨 Get AI Feedback')).toBeInTheDocument();
      });

      const submitBtn = screen.getByText('🎨 Get AI Feedback');
      fireEvent.click(submitBtn);

      // Wait for the second FileReader call (for submission)
      await waitFor(() => {
        const secondReader = global.FileReader.mock.results[1].value;
        secondReader.onloadend();
      });

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          'http://localhost:4000/api/drawing/feedback',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          })
        );
      });

      const call = fetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.skills).toEqual(['Gesture', 'Form (3D Thinking)']);
      expect(body.difficulty).toBe('Intermediate');
      expect(body.exercise).toContain('Practice capturing');
    });

    test('shows loading state during feedback request', async () => {
      fetch.mockImplementationOnce(() => new Promise(() => {}));

      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByText('🎨 Get AI Feedback')).toBeInTheDocument();
      });

      const submitBtn = screen.getByText('🎨 Get AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        const secondReader = global.FileReader.mock.results[1].value;
        secondReader.onloadend();
      });

      await waitFor(() => {
        expect(screen.getByText('Analyzing Your Drawing...')).toBeInTheDocument();
      });
    });

    test('displays feedback after successful request', async () => {
      const mockFeedback = '### Strengths\n\nExcellent gesture lines.\n\n### Areas for Improvement\n\nWork on proportions.';

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ feedback: mockFeedback })
      });

      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByText('🎨 Get AI Feedback')).toBeInTheDocument();
      });

      const submitBtn = screen.getByText('🎨 Get AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        const secondReader = global.FileReader.mock.results[1].value;
        secondReader.onloadend();
      });

      await waitFor(() => {
        expect(screen.getByText('✨ AI Feedback on Your Drawing')).toBeInTheDocument();
        expect(screen.getByText('Strengths')).toBeInTheDocument();
        expect(screen.getByText(/Excellent gesture lines/)).toBeInTheDocument();
      });
    });

    test('displays error on failed request', async () => {
      fetch.mockResolvedValueOnce({
        ok: false,
        status: 500
      });

      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByText('🎨 Get AI Feedback')).toBeInTheDocument();
      });

      const submitBtn = screen.getByText('🎨 Get AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        const secondReader = global.FileReader.mock.results[1].value;
        secondReader.onloadend();
      });

      await waitFor(() => {
        expect(screen.getByText(/Error getting feedback/)).toBeInTheDocument();
      });
    });

    test('handles FileReader errors', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'image/jpeg' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      const mockFileReader = {
        readAsDataURL: jest.fn(),
        onloadend: null,
        onerror: null,
        result: 'data:image/jpeg;base64,mockbase64'
      };

      global.FileReader = jest.fn(() => mockFileReader);

      await userEvent.upload(input, file);
      mockFileReader.onloadend();

      await waitFor(() => {
        expect(screen.getByText('🎨 Get AI Feedback')).toBeInTheDocument();
      });

      const submitBtn = screen.getByText('🎨 Get AI Feedback');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        const secondReader = global.FileReader.mock.results[1].value;
        secondReader.onerror();
      });

      await waitFor(() => {
        expect(screen.getByText(/Failed to read image file/)).toBeInTheDocument();
      });
    });
  });

  describe('Security - File Upload', () => {
    test('rejects executable files disguised as images', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const maliciousFile = new File(['MZ...exe content'], 'malware.exe', { type: 'application/x-msdownload' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      await userEvent.upload(input, maliciousFile);

      await waitFor(() => {
        expect(screen.getByText(/Please upload a JPG or PNG image/)).toBeInTheDocument();
      });
    });

    test('rejects SVG files (potential XSS vector)', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const svgFile = new File(
        ['<svg><script>alert("XSS")</script></svg>'],
        'image.svg',
        { type: 'image/svg+xml' }
      );
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      await userEvent.upload(input, svgFile);

      await waitFor(() => {
        expect(screen.getByText(/Please upload a JPG or PNG image/)).toBeInTheDocument();
      });
    });

    test('enforces strict MIME type checking', async () => {
      renderWithTheme(<DrawingPromptDisplay prompt={mockPrompt} />);

      const file = new File(['dummy'], 'drawing.jpg', { type: 'text/html' });
      const input = screen.getByLabelText(/Click to upload/i, { selector: 'input' });

      await userEvent.upload(input, file);

      await waitFor(() => {
        expect(screen.getByText(/Please upload a JPG or PNG image/)).toBeInTheDocument();
      });
    });
  });
});
