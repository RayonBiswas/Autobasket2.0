import base64

import cv2
import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ImageData(BaseModel):
    image: str

@router.post("/water-level")
def detect_water_level(data: ImageData):

    try:
        # Decode base64 image
        image_data = data.image.split(",")[1]
        decoded = base64.b64decode(image_data)

        np_arr = np.frombuffer(decoded, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            return {"water_percentage": 0, "low": True}

        height = img.shape[0]

        # Convert to HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Blue color range (tune if needed)
        lower_blue = np.array([90, 50, 50])
        upper_blue = np.array([130, 255, 255])

        mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # Count blue pixels row-wise
        row_counts = np.sum(mask > 0, axis=1)

        blue_rows = np.where(row_counts > 10)[0]

        if len(blue_rows) == 0:
            return {"water_percentage": 0, "low": True}

        top_water = min(blue_rows)
        water_height = height - top_water

        water_percentage = int((water_height / height) * 100)

        low = water_percentage < 25

        return {
            "water_percentage": water_percentage,
            "low": low
        }

    except Exception as e:
        return {"error": str(e)}
