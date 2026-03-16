from typing import List, Optional

from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field

import os

app = FirecrawlApp(api_key=os.environ.get("FIRECRAWL_API_KEY", ""))


class ExtractSchema(BaseModel):
    address_road_name: str
    floorplan_images_urls: List[dict]
    image_urls: List[dict]
    source_url: str
    price: str
    address_town: str
    bedrooms_number: float
    estate_agent_name: str
    estate_agent_address: str
    transaction_type_details: str
    bathrooms_number: float
    type: str
    created: str
    address_full: str
    address_postcode: str
    description_full: str
    property_url: str
    description_short: str
    size: str
    tenure: str
    garden: str
    parking: str
    address_location_coordinates: str
    status_availability: str
    last_update_reason: str
    epcs: List[dict]
    train_station_nearby: str
    video_urls: List[dict]
    access: str
    accessibility: str
    flood_risk: str
    heating: str
    listed: str
    restrictions: str
    shared_ownership: str
    utilities: str


def main() -> None:
    result = app.agent(
        schema=ExtractSchema,
        prompt="From this property page: https://www.primelocation.com/to-rent/details/71219657/, I want to get all these details listed below from the property detail page. if the detail isn't present on the page, then put null as the value for that particular key. Ensure that the images gotten are the High resolution images if they exist otherwise get the highest quality images. return an object with all these data as the keys and the extracted information on the page as the value for the corresponding keys:\n\nAddress (Road name)\nFloorplan(s) Images URL(s)\nImage(s) URL(s) (Property photos, ALL, High Res)\nSource URL\nPrice (Sales or Lettings)\nAddress (Town)\nBedrooms (number)\nEstate Agent Name\nEstate Agent Address\nTransaction Type Details (Sales or Rental)\nBathrooms (number)\nType (House, Detatched etc)\nCreated (came to market)\nAddress (min 1st line, max full)\nAddress (Postcode)\nDescription (Full)\nRightmove URL\nDescription (Short)\nSize (if available)\nTenure\nGarden\nParking\nAddress (Location Co-ordinates)\nStatus/Availability\nLast Update & Reason\nEPC(s)\nTrain Station (nearby)\nVideo(s) URLs\nAccess\nAccessibility\nFlood Risk\nHeating\nListed?\nRestrictions\nShared Ownership\nUtilities",
        model="spark-1-mini",
    )
    print(result)


# success=True id=None status='completed' data={'address_road_name': 'Lindale Grove', 'floorplan_images_urls': [], 'image_urls': [{'url': 'https://lid.zoocdn.com/u/1024/768/c3b87e8609b2661f1edbae42cd4bf5f341178b4b.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/71ce96ee25ac1dd9fca07bb097cb6dada1317949.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/fccc0e7c02ce18655665049168e1253d5e01847f.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/79068e07777af768c66a24356580a73c899fbfdc.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/b442ca10ae59f39787c6d771572131bd4ba8aabc.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/04f541df256ea51ef70d97e7936a3493631a119b.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/6125bce6b1f94ea1121bdda0cadefe3c6af5b0b5.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/e322e510e8e30ccfc80d0bf2e4aeee9d6641f6b6.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/17a3f73cf5119cb85e026aaab0635e395a994bef.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/2936a3167c4929e9b6cc5362a2e1a936dc617ce2.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/edf6a231beb3f648bc4a952b24d0673b6920b526.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/996f2c3c6cecca88b461b5990d045ceec9048d16.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/dc7b06d05609aee32ac310578c5117e41df2ccb7.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/d1b1d5505c487573f1261f3717cec64a5bf1b6a0.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/3d9f789ac9d5b0da3f995892de2ec6b65ff4bc83.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/5fd867d448dc2825eb306d8de0b2ab88a9f07040.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/6ec76328e6ff52b8e51e29e2a6730fee3ed36ec7.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/17634a4e1aa8601e599c009fe0620a5d0040dc57.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/b1d5ba5f26d634a05a1b61bc8ab7cbddef765edf.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/f3ecc15752f1ee09d9bc1c7ceb2ea1de8cf545a4.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/6ff5b36af0b5fa3683d2c38609b9dc3075a007f7.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/a5c17a46d9a4f0daf531da8f9b3cdd3efa9a2db9.jpg'}, {'url': 'https://lid.zoocdn.com/u/1024/768/0d33c1c5ff5077f5d6a64966d6775fd830ab3808.jpg'}], 'source_url': 'https://www.primelocation.com/to-rent/details/71219657/', 'price': '£1,600 pcm', 'address_town': 'Wakefield', 'bedrooms_number': 4, 'estate_agent_name': 'Richard Kendall Estate Agent Ltd', 'estate_agent_address': '4 Cluntergate, Horbury, Wakefield, WF4 5AG', 'transaction_type_details': 'Rental', 'bathrooms_number': 2, 'type': 'Detached House', 'created': 'null', 'address_full': 'Lindale Grove, Wakefield WF2 0BU', 'address_postcode': 'WF2 0BU', 'description_full': 'A fabulous, modernised and extended four bedroom detached family home in a popular residential area of Wrenthorpe conveniently located for outstanding primary and secondary schools and amenities as well as good access to nearby transport links including the M1 motorway. The property has undergone a significant upgrade over the past few years and benefits from Smart lighting both inside and out.\n\nAccommodation\nA central entrance hallway leads into the ground floor living accommodation with a useful upgraded w.c. A garage conversion provides a useful snug/office space with adjoining utility room. The hallway leads to the rear of the ground floor where there is a superb open plan living, dining kitchen area.\nThe kitchen is a recent addition with a fridge freezer, dishwasher, double oven and hob. There is also a further well proportioned lounge.\nThe first floor offers four bedrooms, three of which have fitted furniture. There is a stylish en-suite shower room to the master suite and a further en-suite shower to the second large bedroom. A contemporary family bathroom/w.c. completes the first floor.\nOutside is a driveway to the front providing off street parking with two electric car charging points. To the rear is an enclosed garden with patio and lawn and a timber shed.', 'property_url': 'https://www.rightmove.co.uk/properties/166554794', 'description_short': '4‑bed detached house to rent, Lindale Grove, Wakefield WF2 – 4 beds, 2 baths, 2 receptions, part‑furnished, EPC C.', 'size': 'null', 'tenure': 'null', 'garden': 'Enclosed garden with patio and lawn and a timber shed', 'parking': 'Off‑street driveway with parking spaces and two electric car charging points', 'address_location_coordinates': '53.694995, -1.536623', 'status_availability': 'Available Now (Reduced on 10/12/2025)', 'last_update_reason': '10/12/2025 – Reduced', 'epcs': [{'rating': 'C', 'score': 72}], 'train_station_nearby': 'null', 'video_urls': [], 'access': 'null', 'accessibility': 'null', 'flood_risk': 'null', 'heating': 'null', 'listed': 'null', 'restrictions': 'null', 'shared_ownership': 'null', 'utilities': 'null'} error=None expires_at=datetime.datetime(2026, 1, 28, 14, 40, 18, 530000, tzinfo=TzInfo(UTC)) credits_used=0

if __name__ == "__main__":
    main()
    main()
    main()
