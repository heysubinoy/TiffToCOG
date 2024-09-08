from osgeo import gdal
import os
import shutil
import tempfile
import subprocess


import boto3
import validate_cloud_optimized_geotiff as cog_validator

bucket_name = 'final-cog'
s3_key = 'file1.tiff'
def upload_to_s3(local_path):
    session = boto3.Session()
    creds = session.get_credentials()
    creds = creds.get_frozen_credentials()
    
    session = boto3.Session(
    aws_access_key_id=creds.access_key,
    aws_secret_access_key=creds.secret_key,
    region_name='ap-south-1'
)
    s3 = session.client('s3')
    try:
        s3.upload_file(local_path, bucket_name, s3_key)
        print(f"Uploaded {local_path} to S3 bucket {bucket_name} with key {s3_key}.")
    except Exception as e:
        print(f"Error uploading to S3: {e}")

def check_and_convert_tiff(input_path, output_folder):
    """
    Check if a TIFF file is a Cloud Optimized GeoTIFF (COG) and if it uses WGS84 (EPSG:4326).
    If not, convert the TIFF and save to the output folder.
    
    Parameters:
    - input_path: Path to the input TIFF file.
    - output_folder: Directory where the converted TIFF or original TIFF will be saved.
    
    Returns:
    - None
    """
    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)
    
    # Open the TIFF file
    dataset = gdal.Open(input_path)
    if dataset is None:
        print(f"Failed to open file: {input_path}")
        return
    
    # Validate if the TIFF is a COG
    warnings, errors, details = cog_validator.validate(input_path, full_check=False)
    is_cog = not errors
    
    # Check for EPSG:4326
    epsg_code = dataset.GetProjection().split('EPSG:')[-1].split(' ')[0]
    is_wgs84 = epsg_code == '4326'
    if not is_wgs84:
        print(f"File is not in EPSG:4326. EPSG code: {epsg_code}")
    
    # Determine output path
    base_name = os.path.basename(input_path)
    output_path = os.path.join(output_folder, base_name)
    
    if is_cog and is_wgs84:
        # COG and EPSG:4326, just copy the file
        shutil.copy(input_path, output_path)
        print(f"File is a valid COG with EPSG:4326. Copied to {output_path}.")
    else:
        # Convert to COG and re-save
        print("Converting file to COG...")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as temp_tiff:
            temp_tiff_name = temp_tiff.name
        
        # Re-save as a COG
        options = [
            '-of', 'COG',
            '-co', 'TILED=YES',
            '-co', 'COMPRESS=DEFLATE',
            '-co', 'BLOCKSIZE=512'
        ]

        # Build the command
        command = ['gdal_translate'] + options + [input_path, temp_tiff_name]

        # Execute the command
        subprocess.run(command, check=True)
        
        # Revalidate the converted COG
        warnings, errors, details = cog_validator.validate(temp_tiff_name, full_check=False)
    
        print(f"Validation results: Warnings: {warnings}, Errors: {errors}")
        if not errors:
            shutil.move(temp_tiff_name, output_path)
            print(f"File converted to COG and saved to {output_path}.")
            upload_to_s3(output_path)
        else:
            print(f"Conversion failed. The converted file still has issues: {errors}")
            os.remove(temp_tiff_name)

# Example usage
input_tiff_path = '/vsis3/kdg-raw/3DIMG_18JUN2024_0330_L1C_SGP_V01R00_IMG_WV.tif'
output_directory = 'converted_tiffs'
check_and_convert_tiff(input_tiff_path, output_directory)
