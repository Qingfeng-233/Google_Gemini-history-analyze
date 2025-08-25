import json
import re
import jieba
from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.')

# 共享数据和辅助函数
data_cache = None

def load_data():
    global data_cache
    if data_cache is None:
        try:
            with open('../processed_history.json', 'r', encoding='utf-8') as f:
                data_cache = json.load(f)
                print(f"成功加载 {len(data_cache)} 条数据")
        except Exception as e:
            print(f"Error loading data: {e}")
            return None
    return data_cache

def parse_date(timestamp):
    # 尝试解析 "2025年8月14日 10:00:08 JST" 格式
    try:
        # 移除时区信息以便解析
        if ' JST' in timestamp:
            timestamp = timestamp.replace(' JST', '')
        
        # 处理可能的格式变化
        import re
        match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2}):(\d{2})', timestamp)
        if match:
            year, month, day, hour, minute, second = match.groups()
            return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
        else:
            print(f"无法解析时间戳: {timestamp}")
            return datetime.min
    except Exception as e:
        print(f"时间解析错误: {e}, 时间戳: {timestamp}")
        return datetime.min

# 全局变量存储停用词
stop_words_set = None

def load_stopwords():
    global stop_words_set
    if stop_words_set is None:
        stop_words_set = set()
        stopword_files = ['stopwords_cn.txt', 'stopwords_scu.txt', 'stopwords_hit.txt']
        
        for filename in stopword_files:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith('#'):  # 忽略注释行和空行
                            stop_words_set.add(word)
                print(f"成功加载停用词文件: {filename}")
            except Exception as e:
                print(f"加载停用词文件失败 {filename}: {e}")
        
        # 添加针对聊天记录的自定义停用词
        custom_stopwords = {
            '主角', '时间', '世界', '问题', '方面', '情况', '东西', '地方', '事情',
            '什么', '怎么', '这个', '那个', '这样', '那样', '现在', '以后', '之前',
            '可能', '应该', '觉得', '感觉', '比较', '非常', '特别', '一些', '很多',
            '所有', '每个', '任何', '其他', '另外', '包括', '关于', '由于', '因为',
            '如果', '虽然', '但是', '然后', '接着', '最后', '首先', '其次', '总之',
            '一般', '通常', '经常', '总是', '从来', '永远', '马上', '立刻', '刚才',
            '以前', '以后', '现在', '将来', '过去', '未来', '今天', '明天', '昨天',
            '用户', '系统', '模型', '数据', '信息', '内容', '结果', '方法', '功能'
        }
        
        stop_words_set.update(custom_stopwords)
        print(f"总共加载停用词: {len(stop_words_set)} 个")
    
    return stop_words_set

def is_stop_word(word):
    # 1. 过滤带数字的词
    if re.search(r'\d', word):
        return True
    
    # 2. 使用专业停用词表
    stopwords = load_stopwords()
    return word in stopwords

def get_word_frequency(text):
    print(f"=== 开始高质量词云分析 ===")
    print(f"原始文本长度: {len(text)} 字符")
    
    # 第一步：文本清洗
    # 去除URL、邮箱、特殊符号等噪音
    clean_text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    clean_text = re.sub(r'\S+@\S+', '', clean_text)
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z\s]', '', clean_text)
    print(f"文本清洗后长度: {len(clean_text)} 字符")
    
    # 第二步：使用jieba进行专业分词
    words = jieba.lcut(clean_text)
    print(f"jieba分词完成，共分出 {len(words)} 个词")
    
    # 第三步：词性标注筛选（只保留名词、动词、形容词）
    import jieba.posseg as pseg
    pos_words = pseg.lcut(clean_text)
    
    # 保留的词性：名词(n)、动词(v)、形容词(a)、专有名词(nr)、地名(ns)、机构名(nt)
    keep_pos = {'n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn', 'a', 'an'}
    
    frequency = {}
    valid_words = []
    
    for word, pos in pos_words:
        # 多层过滤条件
        if (len(word) >= 2 and  # 长度至少2个字符
            any(pos.startswith(p) for p in keep_pos) and  # 词性筛选
            re.search(r'[\u4e00-\u9fa5]', word) and  # 包含中文
            not is_stop_word(word) and  # 不是停用词
            word.strip() and  # 不是空白
            len(set(word)) > 1):  # 避免重复字符如"的的"
            
            frequency[word] = frequency.get(word, 0) + 1
            valid_words.append(word)
    
    print(f"词性筛选后有效词汇: {len(valid_words)} 个")
    print(f"去重后词汇种类: {len(frequency)} 种")
    
    # 第四步：基于词频的智能过滤
    total_words = len(valid_words)
    if total_words == 0:
        return {}
    
    # 计算词频分布统计
    freq_values = list(frequency.values())
    freq_values.sort(reverse=True)
    
    # 动态阈值：去除低频词（出现次数 < 总词数的0.1%）
    min_freq_threshold = max(2, int(total_words * 0.001))
    
    # 去除超高频词（可能是领域通用词）
    max_freq_threshold = int(total_words * 0.05)  # 超过5%的词可能过于通用
    
    # 应用频率过滤
    filtered_by_freq = {}
    for word, count in frequency.items():
        if min_freq_threshold <= count <= max_freq_threshold:
            filtered_by_freq[word] = count
    
    print(f"频率过滤: 最小阈值={min_freq_threshold}, 最大阈值={max_freq_threshold}")
    print(f"频率过滤后词汇: {len(filtered_by_freq)} 个")
    
    # 第五步：提取N-grams（词组）
    # 寻找高频的2-gram组合
    bigrams = {}
    for i in range(len(valid_words) - 1):
        bigram = valid_words[i] + valid_words[i+1]
        if (len(bigram) >= 4 and  # 词组长度至少4个字符
            not is_stop_word(bigram) and
            re.search(r'[\u4e00-\u9fa5]', bigram)):
            bigrams[bigram] = bigrams.get(bigram, 0) + 1
    
    # 将高频词组加入结果
    bigram_threshold = max(2, int(total_words * 0.0005))
    for bigram, count in bigrams.items():
        if count >= bigram_threshold:
            filtered_by_freq[bigram] = count
    
    print(f"添加高频词组后: {len(filtered_by_freq)} 个词汇")
    
    # 第六步：最终质量检查和排序
    # 如果结果太少，适当降低阈值
    if len(filtered_by_freq) < 30:
        min_freq_threshold = max(1, min_freq_threshold // 2)
        filtered_by_freq = {word: count for word, count in frequency.items() 
                           if count >= min_freq_threshold}
        print(f"结果太少，降低阈值到 {min_freq_threshold}，最终词汇: {len(filtered_by_freq)} 个")
    
    # 如果结果太多，保留前200个高频词（增加词汇丰富度）
    if len(filtered_by_freq) > 200:
        sorted_words = sorted(filtered_by_freq.items(), key=lambda x: x[1], reverse=True)
        filtered_by_freq = dict(sorted_words[:200])
        print(f"结果太多，只保留前200个高频词")
    
    print(f"=== 高质量词云分析完成 ===")
    print(f"最终输出词汇数量: {len(filtered_by_freq)}")
    
    return filtered_by_freq

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

def calculate_overview_stats(data):
    if not data:
        return {
            "totalConversations": 0,
            "avgLength": 0,
            "topTag": "无",
            "timeSpan": "无数据"
        }

    # 平均长度
    total_length = sum(
        len(item.get('user_prompt_cleaned', '')) + len(item.get('ai_response_cleaned', ''))
        for item in data
    )
    avg_length = round(total_length / len(data)) if data else 0

    # 最高频标签
    tag_counts = {}
    for item in data:
        for tag in item.get('tags', []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tag = max(tag_counts, key=tag_counts.get) if tag_counts else "无"

    # 时间跨度
    dates = [parse_date(item['timestamp']) for item in data if 'timestamp' in item]
    time_span = "无数据"
    if dates:
        diff_days = (max(dates) - min(dates)).days
        time_span = f"{diff_days} 天"

    return {
        "totalConversations": len(data),
        "avgLength": avg_length,
        "topTag": top_tag,
        "timeSpan": time_span
    }

def calculate_chart_data(data, analysis_type):
    # 兴趣图表
    tag_counts = {}
    for item in data:
        for tag in item.get('tags', []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    interest_chart = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # 时间图表
    time_data = {}
    for item in data:
        date = parse_date(item['timestamp'])
        key = date.strftime('%Y-%m')
        time_data[key] = time_data.get(key, 0) + 1
    time_chart = sorted(time_data.items())

    # 长度图表
    lengths = []
    for item in data:
        if analysis_type == 'user':
            lengths.append(len(item.get('user_prompt_cleaned', '')))
        elif analysis_type == 'ai':
            lengths.append(len(item.get('ai_response_cleaned', '')))
        else:
            lengths.append(len(item.get('user_prompt_cleaned', '')) + len(item.get('ai_response_cleaned', '')))
    
    bins = [0, 100, 500, 1000, 2000, 5000, float('inf')]
    bin_labels = ['0-100', '100-500', '500-1000', '1000-2000', '2000-5000', '5000+']
    bin_counts = [0] * (len(bins) - 1)
    for length in lengths:
        for i in range(len(bins) - 1):
            if bins[i] <= length < bins[i+1]:
                bin_counts[i] += 1
                break
    length_chart = {"labels": bin_labels, "data": bin_counts}

    return {
        "interestChart": interest_chart,
        "timeChart": time_chart,
        "lengthChart": length_chart
    }

def calculate_detailed_stats(data, analysis_type):
    # 标签统计
    tag_counts = {}
    for item in data:
        for tag in item.get('tags', []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    tag_stats = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:15]

    # 情感分析
    positive_words = ['好', '棒', '优秀', '满意', '喜欢', '赞', '完美', '正确', '成功', '有用', '感谢', '谢谢', '不错', '很好']
    negative_words = ['不好', '差', '错误', '失败', '问题', '困难', '麻烦', '不行', '不对', '糟糕', '烦人', '讨厌', '无聊', '失望']
    positive, negative, neutral = 0, 0, 0
    
    for item in data:
        text = ''
        if analysis_type == 'user':
            text = item.get('user_prompt_cleaned', '')
        elif analysis_type == 'ai':
            text = item.get('ai_response_cleaned', '')
        else:
            text = item.get('user_prompt_cleaned', '') + ' ' + item.get('ai_response_cleaned', '')
        
        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)

        if pos_count > neg_count:
            positive += 1
        elif neg_count > pos_count:
            negative += 1
        else:
            neutral += 1
    
    total = positive + negative + neutral if positive + negative + neutral > 0 else 1
    sentiment_stats = {
        "positive": {"count": positive, "percent": round(positive / total * 100)},
        "neutral": {"count": neutral, "percent": round(neutral / total * 100)},
        "negative": {"count": negative, "percent": round(negative / total * 100)},
    }

    return {
        "tagStats": tag_stats,
        "sentimentStats": sentiment_stats
    }


@app.route('/api/analyze', methods=['POST'])
def analyze_data():
    all_data = load_data()
    if all_data is None:
        return jsonify({"error": "Failed to load data"}), 500

    req_data = request.json
    time_range = req_data.get('timeRange', 'all')
    analysis_type = req_data.get('analysisType', 'both')

    # 1. 根据时间过滤数据
    now = datetime.now()
    filtered_data = []
    
    print(f"当前时间: {now}")
    print(f"时间范围: {time_range}")
    
    if time_range == 'all':
        filtered_data = all_data
        print(f"选择全部数据: {len(filtered_data)} 条")
    else:
        time_delta = None
        if time_range == 'week':
            time_delta = timedelta(days=7)
        elif time_range == 'month':
            time_delta = timedelta(days=30)
        
        if time_delta:
            limit_date = now - time_delta
            print(f"时间限制: {limit_date}")
            
            for item in all_data:
                item_date = parse_date(item.get('timestamp', ''))
                if item_date >= limit_date:
                    filtered_data.append(item)
            
            print(f"过滤后数据: {len(filtered_data)} 条")
        else:
            filtered_data = all_data

    # 2. 提取文本用于词云
    text_parts = []
    for item in filtered_data:
        if analysis_type == 'user' and item.get('user_prompt_cleaned'):
            text_parts.append(item['user_prompt_cleaned'])
        elif analysis_type == 'ai' and item.get('ai_response_cleaned'):
            text_parts.append(item['ai_response_cleaned'])
        elif analysis_type == 'both':
            if item.get('user_prompt_cleaned'):
                text_parts.append(item['user_prompt_cleaned'])
            if item.get('ai_response_cleaned'):
                text_parts.append(item['ai_response_cleaned'])
    
    text = ' '.join(text_parts)
    print(f"提取的文本总长度: {len(text)} 字符，来自 {len(filtered_data)} 条对话")
    word_freq = get_word_frequency(text)

    # 3. 并行计算所有统计数据
    overview_stats = calculate_overview_stats(filtered_data)
    chart_data = calculate_chart_data(filtered_data, analysis_type)
    detailed_stats = calculate_detailed_stats(filtered_data, analysis_type)

    # 4. 准备返回的数据
    response_data = {
        "wordCloud": sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:100],
        "overviewStats": overview_stats,
        "chartData": chart_data,
        "detailedStats": detailed_stats
    }
    
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)