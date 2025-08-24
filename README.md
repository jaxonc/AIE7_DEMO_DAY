# S.A.V.E. - Simple Autonomous Validation Engine

S.A.V.E. is an AI-powered chatbot system for food product data queries, UPC validation, and nutritional information lookup. The system uses a LangGraph agent with specialized tools to process natural language queries and retrieve product information from multiple sources.

## Project Structure

```
AIE7_Demo_Day/
├── src/
│   ├── api/              # FastAPI backend
│   ├── frontend/         # Next.js frontend
│   └── utils/            # Agent tools and utilities
└── example_database/     # Sample data
```

## Quick Start

### Prerequisites

- Python 3.13+ with uv package manager
- Node.js 18+ with npm

### Installation

1. Clone the repository and navigate to the project directory
2. Install uv if not already installed:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Start the development environment:
   ```bash
   chmod +x src/start_dev.sh
   ./src/start_dev.sh
   ```

4. Access the application:
   - Frontend: http://localhost:3000
   - API Backend: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Usage

The system accepts natural language queries about food products. Example queries:

- "What are the ingredients for UPC 041548750927?"
- "Validate UPC code 123456789012"
- "Tell me about the nutrition facts for UPC 0-28400-43330-3"
- "What's the UPC for Lay's chips?"
- "Is it gluten free?" (follows up on previous product context)

## System Components

### Agent Tools

- **UPC Extraction**: Extracts UPC codes from natural language
- **UPC Validator**: Validates UPC format and check digits
- **USDA FDC Tool**: Queries USDA Food Data Central for nutritional data
- **OpenFoodFacts Tool**: Retrieves product information via UPC
- **Example Database Tool**: Searches local product knowledge base
- **Extraction Tool**: Processes and extracts product information

### Frontend

- Next.js 14 with TypeScript
- React 18 with modern hooks
- Tailwind CSS for styling
- Real-time chat interface

### Backend

- FastAPI with CORS middleware
- LangGraph agent integration
- Streaming responses
- Session-based memory management

## API Endpoints

- `POST /api/agent/chat` - Main chat interface
- `GET /api/agent/capabilities` - Agent status and tools
- `GET /api/health` - System health check

## Development

### Manual Setup

```bash
# Backend
uv run python -m src.api.app

# Frontend
cd src/frontend && npm run dev
```



## Troubleshooting

- Ensure both backend and frontend services are running
- Check that data files exist in the appropriate directories
- Verify API keys are properly configured
- Monitor console output for import errors

## Project Status

This is a demo day prototype demonstrating AI agent capabilities and modern web development practices in the food technology domain.