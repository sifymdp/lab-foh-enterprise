FROM python:3.13-slim

WORKDIR /app

# ultralytics depends on non-headless opencv, which links libGL and libglib.
# Neither ships in python:*-slim, so `import cv2` fails at startup without them.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# ultralytics pulls torch, whose default PyPI wheels (including linux/arm64)
# now depend on ~2GB of NVIDIA CUDA runtime libraries. Docker Desktop has no
# GPU passthrough, so none of it is usable — install the CPU build first and
# ultralytics' torch>=1.8.0 requirement is already satisfied when it resolves.
RUN pip install --no-cache-dir --retries 5 --timeout 120 \
        --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision

RUN pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
