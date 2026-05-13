
import os
from PIL import Image, ImageDraw, ImageFont

def create_favicon(output_path):
    # Size for standard favicon
    size = (256, 256)
    
    # Colors from CSS
    bg_color = (10, 10, 26, 255)  # #0a0a1a
    text_color = (232, 232, 240, 255)  # #e8e8f0
    dot_color = (68, 138, 255, 255)  # #448aff
    
    # Create image
    img = Image.new('RGBA', size, bg_color)
    draw = ImageDraw.Draw(img)
    
    # Text content
    text = "VSM"
    dot = "."
    
    try:
        # Try to find a monospace font
        font_path = "C:/Windows/Fonts/consola.ttf" # Consolas
        if not os.path.exists(font_path):
            font_path = "C:/Windows/Fonts/cour.ttf" # Courier New
        
        font = ImageFont.truetype(font_path, 160)
    except:
        font = ImageFont.load_default()

    # Calculate text bounding boxes
    text_bbox = draw.textbbox((0, 0), text, font=font)
    dot_bbox = draw.textbbox((0, 0), dot, font=font)
    
    total_width = (text_bbox[2] - text_bbox[0]) + (dot_bbox[2] - dot_bbox[0])
    total_height = max(text_bbox[3] - text_bbox[1], dot_bbox[3] - dot_bbox[1])
    
    # Center text
    x = (size[0] - total_width) // 2
    y = (size[1] - total_height) // 2 - 20 # Adjust for baseline
    
    # Draw VSM
    draw.text((x, y), text, fill=text_color, font=font)
    
    # Draw Dot
    dot_x = x + (text_bbox[2] - text_bbox[0])
    draw.text((dot_x, y), dot, fill=dot_color, font=font)
    
    # Save as ICO (including multiple sizes)
    img.save(output_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    
    # Also save as PNG
    png_path = os.path.join(os.path.dirname(output_path), "icon.png")
    img.save(png_path, format='PNG')
    
    print(f"Favicon created at {output_path}")
    print(f"PNG Icon created at {png_path}")

if __name__ == "__main__":
    create_favicon("frontend/favicon.ico")
