import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def test_image_gen():
    print("Generating test image with Imagen 4.0...")
    try:
        response = client.models.generate_images(
            model='nano-banana-pro-preview',
            prompt='A futuristic space laboratory with glowing holograms',
            config=types.GenerateImagesConfig(
                number_of_images=1,
                # output_mime_type='image/jpeg' # Let's try without this too if needed
            )
        )
        for i, image in enumerate(response.generated_images):
            print(f"Image {i} generated.")
            # Based on current SDK, it might be in image.image_bytes
            # print(dir(image)) # Debugging
            with open(f'test_image_{i}.png', 'wb') as f:
                f.write(image.image.image_bytes)
        print("Success! Test image saved as test_image_0.png")
    except Exception as e:
        print(f"Failed to generate image: {e}")

if __name__ == "__main__":
    test_image_gen()
