FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libgdal-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Download GSHHS land/water mask for fire detection (497KB, includes lakes)
RUN mkdir -p data && python -c "import urllib.request; urllib.request.urlretrieve('https://zenodo.org/records/10076199/files/gshhs_land_water_mask_3km_i.tif', 'data/gshhs_land_water_mask_3km_i.tif')"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "src"]
