from flask import Flask, request, jsonify
import os
import shutil
import tempfile
import subprocess
import boto3
import validate_cloud_optimized_geotiff as cog_validator
from osgeo import gdal
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enables CORS for all routes

bucket_name = "final-cog"
input_bucket_name = "kdg-raw"


def upload_to_s3(local_path, s3_key):
    session = boto3.Session()
    creds = session.get_credentials()
    creds = creds.get_frozen_credentials()

    s3 = session.client("s3")
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"Uploaded {local_path} to S3 bucket {bucket_name} with key {s3_key}.")
    except Exception as e:
        print(f"Error uploading to S3: {e}")


def check_and_convert_tiff(input_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    dataset = gdal.Open(input_path)
    if dataset is None:
        return {"error": f"Failed to open file: {input_path}"}

    warnings, errors, details = cog_validator.validate(input_path, full_check=False)
    is_cog = not errors

    epsg_code = dataset.GetProjection().split("EPSG:")[-1].split(" ")[0]
    is_wgs84 = epsg_code == "4326"
    if not is_wgs84:
        print(f"File is not in EPSG:4326. EPSG code: {epsg_code}")
    base_name = os.path.basename(input_path)
    output_path = os.path.join(output_folder, base_name)

    if is_cog and is_wgs84:
        shutil.copy(input_path, output_path)
        print(f"File is a valid COG with EPSG:4326. Copied to {output_path}.")
        upload_to_s3(output_path, base_name)
        print(f"File is a valid COG with EPSG:4326. Copied to {output_path}.")
    else:
        print("Converting file to COG...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tif") as temp_tiff:
            temp_tiff_name = temp_tiff.name

        options = [
            "-of",
            "COG",
            "-co",
            "TILED=YES",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "BLOCKSIZE=512",
        ]

        command = ["gdal_translate"] + options + [input_path, temp_tiff_name]
        subprocess.run(command, check=True)

        warnings, errors, details = cog_validator.validate(
            temp_tiff_name, full_check=False
        )

        if not errors:
            shutil.move(temp_tiff_name, output_path)
            print(f"File converted to COG and saved to {output_path}.")
            upload_to_s3(output_path, base_name)
            return {"message": f"File converted to COG and saved to {output_path}."}
        else:
            os.remove(temp_tiff_name)
            return {
                "error": f"Conversion failed. The converted file still has issues: {errors}"
            }


@app.route("/process_tiff", methods=["POST"])
def process_tiff():
    data = request.json
    file_name = data.get("file_name")
    if not file_name:
        return jsonify({"error": "File name is required"}), 400

    input_tiff_path = f"/vsis3/{input_bucket_name}/{file_name}"
    output_directory = "converted_tiffs"

    result = check_and_convert_tiff(input_tiff_path, output_directory)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
