FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data
ENV PORT=5000
EXPOSE 5000
CMD ["waitress-serve", "--port=5000", "app:app"]
