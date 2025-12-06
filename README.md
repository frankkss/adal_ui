# Flask Chatbot

This project is a simple chatbot application built using Flask. It provides a user-friendly chat interface where users can interact with the chatbot in real-time.

source venv/bin/activate && DEBUG=False PORT=5010 python run.py

## Project Structure

```
flask-chatbot
├── app
│   ├── __init__.py
│   ├── routes.py
│   ├── models.py
│   ├── static
│   │   ├── css
│   │   │   └── style.css
│   │   └── js
│   │       └── chat.js
│   └── templates
│       ├── base.html
│       ├── index.html
│       └── chat.html
├── config.py
├── requirements.txt
├── run.py
└── README.md
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd flask-chatbot
   ```

2. Create a virtual environment:
   ```
   python -m venv env
   ```

3. Activate the virtual environment:
   - On Windows:
     ```
     eenv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source env/bin/activate
     ```

4. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python run.py
   ```

2. Open your web browser and go to `http://127.0.0.1:5000` to access the chatbot interface.

## Features

- Real-time chat interface
- User-friendly design
- Easy to extend and modify

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.