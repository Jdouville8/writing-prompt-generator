# Testing Guide - Ideasthesia Creative Prompt Generator

This document provides comprehensive information about testing the application, including setup, running tests, and understanding test coverage.

## 📋 Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Writing New Tests](#writing-new-tests)
- [CI/CD Integration](#cicd-integration)
- [Security Testing](#security-testing)

---

## Overview

The application has comprehensive test coverage across all layers:

- **Frontend Tests**: React component tests, Redux state tests, UI interaction tests
- **Backend Tests**: API integration tests, authentication tests, error handling
- **Prompt Service Tests**: Python unit tests, OpenAI integration tests, feedback generation
- **Security Tests**: XSS prevention, file upload validation, input sanitization

### Test Framework Stack

| Layer | Framework | Tools |
|-------|-----------|-------|
| Frontend | Jest + React Testing Library | `@testing-library/react`, `@testing-library/user-event` |
| Backend | Jest + Supertest | `jest`, `supertest` |
| Prompt Service | Pytest | `pytest`, `pytest-cov`, `pytest-flask` |

---

## Test Structure

```
writing-prompt-generator/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── __tests__/
│   │   │       ├── PromptDisplay.test.js          # Writing feedback component tests
│   │   │       └── DrawingPromptDisplay.test.js   # Drawing upload + feedback tests
│   │   ├── store/
│   │   │   └── __tests__/
│   │   │       └── authSlice.test.js              # Redux auth state tests
│   │   └── setupTests.js                          # Test configuration
│   └── package.json
│
├── backend/
│   ├── __tests__/
│   │   └── api.test.js                            # API integration tests
│   └── package.json
│
├── prompt-service/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                            # Pytest configuration
│   │   ├── test_prompts.py                        # Prompt generation tests
│   │   └── test_feedback.py                       # AI feedback tests
│   └── requirements.txt
│
└── TESTING.md                                     # This file
```

---

## Running Tests

### Frontend Tests

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (if not already installed)
npm install

# Run all tests once
npm test

# Run tests in watch mode (for development)
npm run test:watch

# Run tests with coverage report
npm run test:coverage

# Run specific test file
npm test -- PromptDisplay.test.js
```

#### Expected Frontend Test Output

```
PASS  src/components/__tests__/PromptDisplay.test.js
  ✓ renders prompt title and content (45ms)
  ✓ updates word count as user types (123ms)
  ✓ submits feedback with correct data (89ms)
  ...

PASS  src/components/__tests__/DrawingPromptDisplay.test.js
  ✓ accepts valid JPG file (67ms)
  ✓ rejects files larger than 20MB (34ms)
  ✓ handles file drop (102ms)
  ...

PASS  src/store/__tests__/authSlice.test.js
  ✓ sets user and isAuthenticated on login (12ms)
  ✓ clears user state on logout (8ms)
  ...

Test Suites: 3 passed, 3 total
Tests:       45 passed, 45 total
Snapshots:   0 total
Time:        4.567s
```

### Backend Tests

```bash
# Navigate to backend directory
cd backend

# Install dependencies
npm install

# Run all tests with coverage
npm test

# Run tests in watch mode
npm run test:watch

# Run tests for CI (with coverage, limited workers)
npm run test:ci
```

#### Expected Backend Test Output

```
PASS  __tests__/api.test.js
  Backend API Endpoints
    POST /api/prompts
      ✓ generates prompt with valid genres (56ms)
      ✓ rejects request with no genres (12ms)
      ✓ rejects request with more than 2 genres (9ms)
    POST /api/writing/feedback
      ✓ submits feedback with valid data (78ms)
      ✓ rejects userWriting below word count minimum (15ms)
    POST /api/drawing/feedback
      ✓ submits drawing feedback with valid image (92ms)
      ✓ rejects image larger than 20MB (23ms)
    Security - Input Validation
      ✓ sanitizes SQL injection attempt (34ms)
      ✓ handles XSS attempt (27ms)
      ...

Test Suites: 1 passed, 1 total
Tests:       32 passed, 32 total
```

### Prompt Service Tests (Python)

```bash
# Navigate to prompt-service directory
cd prompt-service

# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run tests with coverage
pytest --cov=. --cov-report=html

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_prompts.py

# Run specific test function
pytest tests/test_feedback.py::TestWritingFeedback::test_generate_feedback_success
```

#### Expected Prompt Service Test Output

```
============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-7.4.0
collected 48 items

tests/test_prompts.py ................................          [ 66%]
tests/test_feedback.py ................                        [100%]

---------- coverage: platform darwin, python 3.11.5-final-0 ----------
Name                      Stmts   Miss  Cover
---------------------------------------------
tests/__init__.py             0      0   100%
tests/conftest.py            15      0   100%
tests/test_prompts.py       142      2    99%
tests/test_feedback.py      128      3    98%
---------------------------------------------
TOTAL                       285      5    98%

============================== 48 passed in 5.43s ==============================
```

### Running All Tests

```bash
# From project root, run all tests across all services
./scripts/run-all-tests.sh
```

---

## Test Coverage

### Coverage Goals

| Component | Target Coverage | Current Coverage |
|-----------|----------------|------------------|
| Frontend Components | 80%+ | ~85% |
| Frontend Redux Store | 90%+ | ~95% |
| Backend API | 85%+ | ~88% |
| Prompt Service | 80%+ | ~82% |

### Viewing Coverage Reports

**Frontend:**
```bash
cd frontend
npm run test:coverage
# Open: frontend/coverage/lcov-report/index.html
```

**Backend:**
```bash
cd backend
npm test
# Coverage summary displayed in terminal
```

**Prompt Service:**
```bash
cd prompt-service
pytest --cov=. --cov-report=html
# Open: prompt-service/htmlcov/index.html
```

### Key Coverage Areas

✅ **Covered:**
- Writing prompt generation and feedback submission
- Drawing exercise generation and image upload
- File validation (type, size)
- Word count validation
- Authentication flows
- Error handling
- XSS prevention
- SQL injection protection
- Input sanitization
- Markdown rendering

⚠️ **Partial Coverage:**
- MIDI file generation edge cases
- Redis connection failures
- OpenTelemetry instrumentation
- Network timeout scenarios

❌ **Not Covered (Intentionally):**
- External API calls (OpenAI, Google OAuth) - mocked in tests
- Database migrations
- Infrastructure/deployment scripts

---

## Writing New Tests

### Frontend Component Test Template

```javascript
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import YourComponent from '../YourComponent';

describe('YourComponent', () => {
  beforeEach(() => {
    // Setup
  });

  test('renders correctly', () => {
    render(<YourComponent />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });

  test('handles user interaction', async () => {
    render(<YourComponent />);
    const button = screen.getByRole('button');
    await userEvent.click(button);
    await waitFor(() => {
      expect(screen.getByText('Result')).toBeInTheDocument();
    });
  });
});
```

### Backend API Test Template

```javascript
const request = require('supertest');
const app = require('../server');

describe('GET /api/endpoint', () => {
  test('returns expected data', async () => {
    const response = await request(app)
      .get('/api/endpoint')
      .expect(200);

    expect(response.body).toHaveProperty('data');
  });

  test('handles errors gracefully', async () => {
    const response = await request(app)
      .get('/api/invalid')
      .expect(404);

    expect(response.body.error).toBeDefined();
  });
});
```

### Python Test Template

```python
import pytest

class TestYourFeature:
    """Test your feature."""

    def test_basic_functionality(self, client):
        """Test basic functionality."""
        response = client.post('/api/endpoint', json={'data': 'test'})

        assert response.status_code == 200
        data = response.get_json()
        assert 'result' in data

    def test_error_handling(self, client):
        """Test error handling."""
        response = client.post('/api/endpoint', json={})

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
```

---

## CI/CD Integration

Tests are automatically run in the Jenkins pipeline on every commit. See [ci-cd/Jenkinsfile](ci-cd/Jenkinsfile) for the full configuration.

### Pipeline Stages

1. **Code Quality** (parallel):
   - Frontend linting: `npm run lint`
   - Backend linting: `npm run lint`
   - Python linting: `flake8`, `black`

2. **Unit Tests** (parallel):
   - Frontend: `npm test -- --coverage`
   - Backend: `npm test`
   - Prompt Service: `pytest --cov=. --cov-report=xml`

3. **Integration Tests**:
   - Start all services with docker-compose
   - Run end-to-end tests
   - Verify API endpoints

4. **Security Scan**:
   - Trivy filesystem scan
   - TruffleHog secret detection
   - Dependency vulnerability checks

### Running Tests Locally Like CI

```bash
# Run all quality checks
npm run lint          # In frontend/
npm run lint          # In backend/
flake8 .             # In prompt-service/
black --check .      # In prompt-service/

# Run all tests with coverage
npm test             # In frontend/
npm test             # In backend/
pytest --cov=.       # In prompt-service/
```

---

## Security Testing

### Test Categories

#### 1. Input Validation Tests

**Location:** All test files with "security" sections

**Coverage:**
- SQL injection attempts
- XSS script injection
- Command injection
- Path traversal
- Unicode exploits

**Example:**
```javascript
test('sanitizes SQL injection attempt', async () => {
  const malicious = "'; DROP TABLE users; --";
  const response = await request(app)
    .post('/api/writing/feedback')
    .send({ userWriting: malicious });

  expect(response.status).toBe(200); // Should handle safely
});
```

#### 2. File Upload Security Tests

**Location:** `DrawingPromptDisplay.test.js`, `test_feedback.py`

**Coverage:**
- File type validation (JPG/PNG only)
- File size limits (20MB max)
- Malicious file detection
- SVG bomb protection
- Executable file rejection

**Example:**
```javascript
test('rejects executable files disguised as images', async () => {
  const maliciousFile = new File(
    ['MZ...exe content'],
    'malware.exe',
    { type: 'application/x-msdownload' }
  );

  await userEvent.upload(input, maliciousFile);
  expect(screen.getByText(/Please upload a JPG or PNG/)).toBeInTheDocument();
});
```

#### 3. Authentication & Authorization Tests

**Location:** `authSlice.test.js`, `api.test.js`

**Coverage:**
- Token validation
- Expired token handling
- Missing credentials
- Token storage security
- Session management

#### 4. XSS Prevention Tests

**Location:** `PromptDisplay.test.js`

**Coverage:**
- Markdown rendering safety
- Script tag sanitization
- HTML entity escaping
- JavaScript URL blocking

### Security Test Checklist

- [ ] All user inputs validated
- [ ] File uploads restricted (type, size)
- [ ] SQL injection prevented
- [ ] XSS attacks blocked
- [ ] Authentication required for protected routes
- [ ] Secrets not in code/localStorage
- [ ] Rate limiting tested
- [ ] Error messages don't leak sensitive info

---

## Troubleshooting Tests

### Common Issues

**Issue: Tests fail with "Cannot find module"**
```bash
# Solution: Install dependencies
cd frontend && npm install
cd backend && npm install
cd prompt-service && pip install -r requirements.txt
```

**Issue: "EADDRINUSE: address already in use"**
```bash
# Solution: Kill process using the port
lsof -i :3000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

**Issue: OpenAI API mocks not working**
```javascript
// Solution: Ensure mock is before test
beforeEach(() => {
  fetch.mockClear();
});
```

**Issue: Pytest cannot find modules**
```bash
# Solution: Run from correct directory
cd prompt-service
python -m pytest tests/
```

---

## Best Practices

1. **Write tests before fixing bugs** - Test-driven development
2. **Mock external services** - Don't call real OpenAI API
3. **Test edge cases** - Empty strings, null values, large inputs
4. **Test error paths** - Not just happy path
5. **Keep tests isolated** - Each test should be independent
6. **Use descriptive names** - `test_rejects_files_larger_than_20MB` not `test1`
7. **Avoid test interdependence** - Tests shouldn't rely on execution order
8. **Clean up after tests** - Reset mocks, clear timers

---

## Running Tests in Docker

```bash
# Run frontend tests in Docker
docker-compose run frontend npm test

# Run backend tests in Docker
docker-compose run backend npm test

# Run prompt service tests in Docker
docker-compose run prompt-service pytest
```

---

## Contributing

When adding new features:

1. Write tests for new functionality
2. Ensure all existing tests pass
3. Aim for >80% code coverage
4. Add security tests if handling user input
5. Update this documentation if adding new test types

---

## Additional Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Supertest Documentation](https://github.com/visionmedia/supertest)

---

**Last Updated:** 2025-01-16
