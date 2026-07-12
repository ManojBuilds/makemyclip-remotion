import cv2
import numpy as np

bg = np.zeros((500, 500, 3), dtype=np.uint8)
fg = np.ones((200, 300, 3), dtype=np.uint8) * 100

def blend_rounded_rect(bg, fg, y, x, radius=30):
    H, W = fg.shape[:2]
    
    # Create mask
    mask = np.zeros((H, W), dtype=np.float32)
    cv2.rectangle(mask, (radius, 0), (W-radius, H), 1.0, -1)
    cv2.rectangle(mask, (0, radius), (W, H-radius), 1.0, -1)
    cv2.circle(mask, (radius, radius), radius, 1.0, -1, cv2.LINE_AA)
    cv2.circle(mask, (W-radius, radius), radius, 1.0, -1, cv2.LINE_AA)
    cv2.circle(mask, (radius, H-radius), radius, 1.0, -1, cv2.LINE_AA)
    cv2.circle(mask, (W-radius, H-radius), radius, 1.0, -1, cv2.LINE_AA)
    
    # Draw border
    border_color = (255, 255, 255)
    thick = 4
    # Horizontal
    cv2.line(fg, (radius, thick//2), (W-radius, thick//2), border_color, thick)
    cv2.line(fg, (radius, H-thick//2), (W-radius, H-thick//2), border_color, thick)
    # Vertical
    cv2.line(fg, (thick//2, radius), (thick//2, H-radius), border_color, thick)
    cv2.line(fg, (W-thick//2, radius), (W-thick//2, H-radius), border_color, thick)
    
    # Arcs
    cv2.ellipse(fg, (radius, radius), (radius, radius), 0, 180, 270, border_color, thick, cv2.LINE_AA)
    cv2.ellipse(fg, (W-radius, radius), (radius, radius), 0, 270, 360, border_color, thick, cv2.LINE_AA)
    cv2.ellipse(fg, (radius, H-radius), (radius, radius), 0, 90, 180, border_color, thick, cv2.LINE_AA)
    cv2.ellipse(fg, (W-radius, H-radius), (radius, radius), 0, 0, 90, border_color, thick, cv2.LINE_AA)
    
    # Blend
    mask_3c = np.stack([mask]*3, axis=2)
    roi = bg[y:y+H, x:x+W]
    bg[y:y+H, x:x+W] = (fg * mask_3c + roi * (1.0 - mask_3c)).astype(np.uint8)

blend_rounded_rect(bg, fg, 100, 100, 20)
cv2.imwrite("scratch/rounded.jpg", bg)
print("Saved!")
