# Run it 
docker build -t pod-scanner .
docker run -it --rm -p 8000:8000 pod-scanner:latest
# Parralel Processing in Python
ThreadPoolExecutor - I/O-bound tasks 
ProcessPoolExecutor - CPU-bound tasks
asyncio - scalling