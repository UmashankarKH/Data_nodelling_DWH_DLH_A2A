# Packages the Sales Insights A2A agent for Azure Container Apps (or any container host).
# The gold layer is built INSIDE the image, so the container needs no files from your laptop.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
RUN python 01_generate_data.py && python 04_medallion_delta.py
ENV HOST=0.0.0.0 PORT=9999
EXPOSE 9999
CMD ["python", "a2a_server.py"]
