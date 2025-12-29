@echo off
echo Starting Streamlit Energy Efficiency Agent with Ollama...
cd /d %~dp0
start "" streamlit run app.py --server.port 8501
exit
