import requests
import json
import os
import time
from datetime import datetime

# === 用户配置区 ===
COLUMN_ID = "1432825"  # 你要抓取的栏目ID
SAVE_DIR = "./cloudradio_audio"  # 音频文件保存的本地目录
API_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 60
# ==================

def setup_environment():
    """创建保存目录"""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"[信息] 创建保存目录: {SAVE_DIR}")
    else:
        print(f"[信息] 使用现有目录: {SAVE_DIR}")

def fetch_all_programs(column_id):
    """
    核心函数：获取所有节目数据
    返回：节目列表，或出错时返回None
    """
    api_url = "https://ytmsout.radio.cn/web/appProgram/pageByColumn"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0',
        'Referer': 'https://www.radio.cn/',
        'Origin': 'https://www.radio.cn',
        'Accept': 'application/json',
        'platformcode': 'WEB',
        'equipmentid': '0000',
        'timestamp': os.getenv('YT_TIMESTAMP', ''),  # 从环境变量读取
        'sign': os.getenv('YT_SIGN', ''),            # 从环境变量读取
        'Host': 'ytmsout.radio.cn'
    }

    all_programs = []
    page_no = 0
    page_size = 20
    max_retries = 3  # 每页请求失败重试次数

    print(f"[信息] 开始抓取栏目 {column_id} 的节目...")

    while True:
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            try:
                params = {'pageNo': page_no, 'columnId': column_id, 'pageSize': page_size}
                print(f"[请求] 第 {page_no + 1} 页，尝试 {retry_count + 1}/{max_retries}...")

                resp = requests.get(api_url, headers=headers, params=params, timeout=API_TIMEOUT)
                resp.raise_for_status()  # 检查HTTP状态码

                data = resp.json()
                print(f"[响应] 状态码: {resp.status_code}, 业务码: {data.get('code')}")

                if data.get('code') == 0 and data.get('data'):
                    program_list = data['data'].get('data', [])
                    total_page = data['data'].get('totalPage', 1)
                    total_num = data['data'].get('totalNum', 0)

                    if not program_list:
                        print(f"[信息] 第 {page_no + 1} 页数据为空，停止抓取。")
                        success = True
                        break

                    all_programs.extend(program_list)
                    print(f"[成功] 第 {page_no + 1} 页，获取 {len(program_list)} 条，累计 {len(all_programs)} 条。")
                    print(f"[进度] 总页数: {total_page}, 总条数: {total_num}")

                    # 判断是否已抓取完所有页面
                    if page_no >= total_page - 1:
                        print(f"[信息] 已到达最后一页（共 {total_page} 页）。")
                        success = True
                        break

                    page_no += 1
                    success = True
                    time.sleep(1)  # 礼貌延迟，避免请求过快

                else:
                    print(f"[警告] API返回异常数据: {data.get('message', '未知错误')}")
                    retry_count += 1
                    time.sleep(2)

            except requests.exceptions.RequestException as e:
                print(f"[网络错误] 第 {page_no + 1} 页请求失败: {e}")
                retry_count += 1
                time.sleep(3)
            except json.JSONDecodeError as e:
                print(f"[解析错误] 响应不是有效JSON: {e}")
                retry_count += 1
                time.sleep(2)

        # 如果重试多次仍失败，则终止
        if not success:
            print(f"[严重错误] 第 {page_no + 1} 页经过 {max_retries} 次重试仍失败，停止抓取。")
            return None

        # 如果上一轮循环因数据空或到达末页而break，则跳出主循环
        if not program_list or page_no >= total_page - 1:
            break

    print(f"[完成] 数据抓取结束，共获取 {len(all_programs)} 个节目。")
    return all_programs

def download_audio_files(program_list):
    """下载所有音频文件"""
    if not program_list:
        print("[错误] 节目列表为空，无法下载。")
        return

    downloaded_count = 0
    error_count = 0
    skipped_count = 0

    print(f"\n[信息] 开始下载音频文件，共 {len(program_list)} 个...")

    for i, program in enumerate(program_list, 1):
        download_url = program.get('downloadUrl')
        program_name = program.get('name', f'未知节目_{i}').strip()
        program_date = program.get('programDate')

        if not download_url:
            print(f"[跳过] {i}/{len(program_list)}: 节目 '{program_name}' 无下载链接。")
            error_count += 1
            continue

        # 生成文件名
        if program_date:
            try:
                date_obj = datetime.fromtimestamp(int(program_date) / 1000)
                date_str = date_obj.strftime('%Y%m%d')
            except (ValueError, TypeError, OSError):
                date_str = '无日期'
        else:
            date_str = '无日期'

        # 清理文件名，移除路径非法字符
        safe_name = "".join(c for c in program_name if c.isalnum() or c in (' ', '-', '_', '(', ')', '（', '）')).strip()
        safe_name = safe_name[:80]  # 防止文件名过长
        file_name = f"{date_str}_{safe_name}.mp3"
        file_path = os.path.join(SAVE_DIR, file_name)

        # 检查文件是否已存在
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / 1024  # KB
            print(f"[跳过] {i}/{len(program_list)}: 文件已存在 ({file_size:.1f}KB) -> {file_name}")
            skipped_count += 1
            continue

        # 开始下载
        print(f"[下载] {i}/{len(program_list)}: {file_name}")
        try:
            # 注意：下载请求可能不需要复杂的请求头
            file_headers = {'User-Agent': 'Mozilla/5.0'}
            audio_resp = requests.get(download_url, headers=file_headers, stream=True, timeout=DOWNLOAD_TIMEOUT)
            audio_resp.raise_for_status()

            total_size = int(audio_resp.headers.get('content-length', 0))
            downloaded_size = 0

            with open(file_path, 'wb') as f:
                for chunk in audio_resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            percent = (downloaded_size / total_size) * 100
                            # 简单进度显示，每10%打印一次
                            if int(percent) % 10 == 0 and int(percent) > 0:
                                print(f"      进度: {percent:.0f}% ({downloaded_size/1024:.1f}KB/{total_size/1024:.1f}KB)")

            # 验证文件大小
            actual_size = os.path.getsize(file_path)
            if total_size > 0 and actual_size != total_size:
                print(f"[警告] 文件大小不匹配: 期望 {total_size} 字节, 实际 {actual_size} 字节")
            else:
                print(f"[成功] 下载完成 ({actual_size/1024:.1f}KB)。")
                downloaded_count += 1

        except Exception as e:
            print(f"[失败] 下载出错: {e}")
            # 删除可能不完整的文件
            if os.path.exists(file_path):
                os.remove(file_path)
            error_count += 1

        # 请求间隔，避免对服务器造成压力
        time.sleep(0.8)

    # 下载总结
    print(f"\n[下载总结]")
    print(f"  成功: {downloaded_count} 个")
    print(f"  跳过: {skipped_count} 个 (已存在)")
    print(f"  失败: {error_count} 个")
    print(f"  文件保存至: {os.path.abspath(SAVE_DIR)}")

def main():
    """主函数"""
    print("=" * 50)
    print("云听音频一次性抓取工具")
    print("=" * 50)

    # 1. 准备环境
    setup_environment()

    # 2. 获取所有节目数据
    all_programs = fetch_all_programs(COLUMN_ID)

    if all_programs is None:
        print("[错误] 获取节目数据失败，程序终止。")
        return

    if len(all_programs) == 0:
        print("[警告] 未获取到任何节目数据。")
        return

    # 3. 下载音频文件
    download_audio_files(all_programs)

    print("\n[全部完成] 一次性抓取任务结束！")

if __name__ == "__main__":
    main()
