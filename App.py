import webview

URL = (
    "https://studio.tripo3d.ai/3d-model/"
    "anime-girl-with-dark-hair-in-a-black-and-pink-school-uniform-"
    "wielding-bc97148a-4c5b-4196-a3ed-57cea8530be6"
)

def main():
    window = webview.create_window(
        title="Tripo3D - Anime Girl 3D Model",
        url=URL,
        width=1280,
        height=800,
        resizable=True,
    )
    webview.start()

if __name__ == "__main__":
    main()
