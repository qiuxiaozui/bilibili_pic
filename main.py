import requests
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from PIL import Image, ImageTk
from io import BytesIO


class BilibiliDynamicDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("B站动态下载器")
        self.root.geometry("600x400")

        # 用户ID输入
        ttk.Label(root, text="UP主ID:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.mid_entry = ttk.Entry(root, width=30)
        self.mid_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 下载类型选择
        self.download_type = tk.StringVar(value="image")
        ttk.Radiobutton(root, text="下载图片", variable=self.download_type, value="image").grid(
            row=1, column=0, padx=5, pady=5)
        ttk.Radiobutton(root, text="下载文字动态", variable=self.download_type, value="text").grid(
            row=1, column=1, padx=5, pady=5)

        # 数量限制
        ttk.Label(root, text="数量限制:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.limit_entry = ttk.Entry(root, width=10)
        self.limit_entry.insert(0, "10")
        self.limit_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        # 保存路径
        ttk.Label(root, text="保存路径:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.path_entry = ttk.Entry(root, width=40)
        self.path_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(root, text="浏览...", command=self.select_path).grid(row=3, column=2, padx=5,
                                                                        pady=5)

        # 预览区域
        self.preview_label = ttk.Label(root, text="预览将显示在这里")
        self.preview_label.grid(row=4, column=0, columnspan=3, padx=5, pady=5)

        # 进度条
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=3, padx=5, pady=5)

        # 开始按钮
        ttk.Button(root, text="开始下载", command=self.start_download).grid(row=6, column=1, padx=5,
                                                                            pady=10)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("准备就绪")
        ttk.Label(root, textvariable=self.status_var).grid(row=7, column=0, columnspan=3, padx=5,
                                                           pady=5)

        # 初始化cookies和headers
        self.cookies = {
            'buvid3': 'E6DE022D-D8A9-6A9C-49E0-87E3AD097DEF58846infoc',
            # ... 其他cookies ...
        }

    def select_path(self):
        path = filedialog.askdirectory()
        if path:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, path)

    def start_download(self):
        host_mid = self.mid_entry.get()
        if not host_mid:
            messagebox.showerror("错误", "请输入UP主ID")
            return

        try:
            num_limit = int(self.limit_entry.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数量")
            return

        path = self.path_entry.get()
        if not path:
            messagebox.showerror("错误", "请选择保存路径")
            return

        if not os.path.exists(path):
            os.makedirs(path)

        download_type = self.download_type.get()

        # 在新线程中执行下载，避免界面冻结
        threading.Thread(
            target=self.download_content,
            args=(host_mid, num_limit, path, download_type),
            daemon=True
        ).start()

    def download_content(self, host_mid, num_limit, path, download_type):
        self.status_var.set("正在连接B站服务器...")
        self.root.update()

        try:
            if download_type == "image":
                self.download_images(host_mid, num_limit, path)
            else:
                self.download_texts(host_mid, num_limit, path)

            self.status_var.set("下载完成！")
            messagebox.showinfo("完成", "下载任务已完成")
        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")
            messagebox.showerror("错误", f"下载过程中出现错误: {str(e)}")

    def download_images(self, host_mid, num_limit, path):
        offset = None
        url_list = []

        while len(url_list) < num_limit:
            response = requests.get(
                'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?',
                params=self.get_params(offset=offset, host_mid=host_mid),
                cookies=self.cookies,
                headers=self.get_headers(host_mid),
            )

            if response.status_code != 200:
                raise Exception(f"请求失败，状态码: {response.status_code}")

            data = response.json().get('data')
            if not data:
                break

            items = data.get('items', [])
            offset = data.get('offset')

            if not items or not offset:
                break

            for item in items:
                if len(url_list) >= num_limit:
                    break

                module = item.get('modules', {}).get('module_dynamic', {})
                major = module.get('major')

                if not major:
                    continue

                # 处理opus类型的动态(多图)
                if 'opus' in major:
                    pics = major['opus'].get('pics', [])
                    for pic in pics:
                        if len(url_list) >= num_limit:
                            break
                        pic_url = pic.get('url')
                        if pic_url and pic_url not in url_list:
                            url_list.append(pic_url)
                            self.update_preview(pic_url)

                # 处理archive类型的动态(视频封面)
                elif 'archive' in major:
                    cover = major['archive'].get('cover')
                    if cover and cover not in url_list:
                        url_list.append(cover)
                        self.update_preview(cover)

            self.progress['value'] = len(url_list) / num_limit * 100
            self.status_var.set(f"已找到 {len(url_list)}/{num_limit} 张图片")
            self.root.update()

        # 下载图片
        self.status_var.set(f"开始下载 {len(url_list)} 张图片...")
        self.root.update()

        for i, url in enumerate(url_list):
            try:
                img_data = requests.get(url).content
                name = url.split('/')[-1].split('?')[0]
                with open(os.path.join(path, name), 'wb') as f:
                    f.write(img_data)

                self.progress['value'] = (i + 1) / len(url_list) * 100
                self.status_var.set(f"下载进度: {i + 1}/{len(url_list)}")
                self.root.update()
            except Exception as e:
                print(f"下载 {url} 失败: {str(e)}")

    def download_texts(self, host_mid, num_limit, path):
        offset = None
        desc_list = []

        while len(desc_list) < num_limit:
            response = requests.get(
                'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?',
                params=self.get_params(offset=offset, host_mid=host_mid),
                cookies=self.cookies,
                headers=self.get_headers(host_mid),
            )

            if response.status_code != 200:
                raise Exception(f"请求失败，状态码: {response.status_code}")

            data = response.json().get('data')
            if not data:
                break

            items = data.get('items', [])
            offset = data.get('offset')

            if not items or not offset:
                break

            for item in items:
                if len(desc_list) >= num_limit:
                    break

                desc = item.get('modules', {}).get('module_dynamic', {}).get('desc')
                if not desc:
                    continue

                rich_text_nodes = desc.get('rich_text_nodes', [])
                if rich_text_nodes:
                    text = ''.join([node.get('text', '') for node in rich_text_nodes])
                else:
                    text = str(desc)

                desc_list.append(text)
                self.status_var.set(f"已获取 {len(desc_list)}/{num_limit} 条动态")
                self.progress['value'] = len(desc_list) / num_limit * 100
                self.root.update()

        # 保存到文件
        with open(os.path.join(path, '文字动态.txt'), 'w', encoding='utf-8') as f:
            for i, desc in enumerate(desc_list):
                f.write(f"动态 {i + 1}:\n{desc}\n\n{'=' * 50}\n\n")

    def update_preview(self, image_url):
        try:
            response = requests.get(image_url)
            img_data = response.content
            img = Image.open(BytesIO(img_data))
            img.thumbnail((300, 300))
            photo = ImageTk.PhotoImage(img)

            self.preview_label.config(image=photo)
            self.preview_label.image = photo  # 保持引用
        except Exception as e:
            print(f"预览更新失败: {str(e)}")

    def get_params(self, offset, host_mid):
        return {
        "offset": offset,
        "host_mid": host_mid,
        "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,forwardListHidden,decorationCard,commentsNewVersion,onlyfansAssetsV2,ugcDelete,onlyfansQaCard",
        "dm_img_list": '[{"x":2316,"y":1662,"z":0,"timestamp":607,"k":65,"type":0},{"x":1622,'
                       '"y":736,"z":2,"timestamp":774,"k":111,"type":0},{"x":1714,"y":24,"z":114,'
                       '"timestamp":875,"k":84,"type":0},{"x":1514,"y":-487,"z":42,"timestamp":1064,"k":96,"type":0},{"x":1734,"y":-313,"z":193,"timestamp":1182,"k":101,"type":0},{"x":2138,"y":103,"z":262,"timestamp":1315,"k":120,"type":0},{"x":2265,"y":226,"z":332,"timestamp":1427,"k":100,"type":0},{"x":2519,"y":481,"z":583,"timestamp":2623,"k":75,"type":0},{"x":2062,"y":194,"z":76,"timestamp":2724,"k":62,"type":0},{"x":2308,"y":791,"z":74,"timestamp":2825,"k":85,"type":0},{"x":2867,"y":1360,"z":626,"timestamp":2926,"k":83,"type":0},{"x":2452,"y":952,"z":213,"timestamp":3026,"k":70,"type":0},{"x":3159,"y":1660,"z":917,"timestamp":3174,"k":86,"type":0},{"x":2923,"y":1671,"z":377,"timestamp":3275,"k":79,"type":0},{"x":3729,"y":1927,"z":993,"timestamp":14049,"k":96,"type":0},{"x":4396,"y":2491,"z":1693,"timestamp":14151,"k":72,"type":0},{"x":3059,"y":1085,"z":287,"timestamp":14254,"k":110,"type":0},{"x":4382,"y":2151,"z":1553,"timestamp":16488,"k":85,"type":0},{"x":4384,"y":1567,"z":1703,"timestamp":16589,"k":112,"type":0},{"x":3297,"y":489,"z":589,"timestamp":16690,"k":78,"type":0},{"x":3944,"y":1266,"z":984,"timestamp":16800,"k":96,"type":0},{"x":2996,"y":673,"z":190,"timestamp":73046,"k":91,"type":0},{"x":3642,"y":1042,"z":1230,"timestamp":73148,"k":75,"type":0},{"x":3722,"y":1085,"z":1329,"timestamp":73250,"k":99,"type":0},{"x":2714,"y":91,"z":325,"timestamp":73351,"k":81,"type":0},{"x":4237,"y":1671,"z":1861,"timestamp":73451,"k":84,"type":0},{"x":4634,"y":2075,"z":2260,"timestamp":73551,"k":117,"type":0},{"x":2697,"y":156,"z":315,"timestamp":73652,"k":75,"type":0},{"x":2706,"y":181,"z":322,"timestamp":73753,"k":64,"type":0},{"x":4153,"y":1630,"z":1763,"timestamp":73855,"k":73,"type":0},{"x":3176,"y":662,"z":782,"timestamp":74174,"k":124,"type":0},{"x":4505,"y":2024,"z":2104,"timestamp":74278,"k":61,"type":0},{"x":5157,"y":2698,"z":2759,"timestamp":74379,"k":95,"type":0},{"x":6084,"y":3632,"z":3688,"timestamp":74575,"k":111,"type":0},{"x":3133,"y":780,"z":762,"timestamp":74677,"k":101,"type":0},{"x":3089,"y":759,"z":718,"timestamp":74770,"k":90,"type":0}]',
        "dm_img_str": "V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ",
        "dm_cover_img_str": "QU5HTEUgKE5WSURJQSwgTlZJRElBIEdlRm9yY2UgR1RYIDEwNjAgKDB4MDAwMDFDMjApIERpcmVjdDNEMTEgdnNfNV8wIHBzXzVfMCwgRDNEMTEpR29vZ2xlIEluYy4gKE5WSURJQS",
    }

    def get_headers(self, host_mid):
        return {
        'accept': '*/*',
        'accept-language': 'zh,en;q=0.9,zh-CN;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'priority': 'u=1, i',
        'referer': 'https://space.bilibili.com/'+
                   host_mid + '/dynamic?spm_id_from=333.1387.list.card_title.click',
        'sec-ch-ua': '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
    }


if __name__ == '__main__':
    root = tk.Tk()
    app = BilibiliDynamicDownloader(root)
    root.mainloop()