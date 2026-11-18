import socket
import tkinter as tk


OSC_HOST = "127.0.0.1"
OSC_PORT = 8001
SHADERS = {
    "Blob": "blob",
    "Gradient": "shader",
}


def osc_string(value):
    encoded = value.encode("utf-8") + b"\0"
    return encoded + b"\0" * (-len(encoded) % 4)


def send_shader(name):
    packet = osc_string("/shader") + osc_string(",s") + osc_string(name)
    udp_socket.sendto(packet, (OSC_HOST, OSC_PORT))
    status.set(f"Selected: {name}")


udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
root = tk.Tk()
root.title("Shader menu")
root.configure(bg="#171923")
root.attributes("-topmost", True)
root.overrideredirect(True)

panel_width = 460
panel_height = 104
x_position = (root.winfo_screenwidth() - panel_width) // 2
y_position = root.winfo_screenheight() - panel_height - 18
root.geometry(f"{panel_width}x{panel_height}+{x_position}+{y_position}")

title = tk.Label(
    root,
    text="SHADER",
    bg="#171923",
    fg="#a0aec0",
    font=("TkDefaultFont", 9, "bold"),
)
title.pack(pady=(8, 2))

buttons = tk.Frame(root, bg="#171923")
buttons.pack()
for label, name in SHADERS.items():
    tk.Button(
        buttons,
        text=label,
        command=lambda selected=name: send_shader(selected),
        bg="#343b4b",
        fg="white",
        activebackground="#52617a",
        activeforeground="white",
        relief="flat",
        padx=22,
        pady=6,
    ).pack(side="left", padx=6)

status = tk.StringVar(value="Choose a shader")
tk.Label(
    root,
    textvariable=status,
    bg="#171923",
    fg="#cbd5e0",
    font=("TkDefaultFont", 9),
).pack(pady=(4, 0))

root.bind("<Escape>", lambda _event: root.destroy())
root.mainloop()
udp_socket.close()
