// 凤凰秀直播/回放 Worker

// 频道配置
const channels = {
    'fhzw': 'f7f48462-9b13-485b-8101-7b54716411ec',  // 凤凰中文
    'fhzx': '7c96b084-60e1-40a9-89c5-682b994fb680',  // 凤凰资讯
    'fhhk': '15e02d92-1698-416c-af2f-3e9a872b4d78',  // 凤凰深圳
};

// 账号配置（可选，不填则用无token模式）
const ACCOUNT_CONFIG = {
    phone_prefix: '86',      // 手机号前缀
    phone: '',               // 手机号，不填则用无token模式
    password: ''             // 密码，不填则用无token模式
};

// KV命名空间绑定（用于存储token），需要在wrangler.toml中配置
// 如果不使用KV，可以注释掉相关代码

/**
 * 获取token（带30天缓存）
 */
async function getToken(env, prefix, phone, pwd) {
    // 如果没有账号，直接返回空
    if (!phone || !pwd) {
        return '';
    }
    
    // 使用KV存储token
    if (env && env.FENGSHOWS_TOKEN) {
        const cached = await env.FENGSHOWS_TOKEN.get('token');
        if (cached) {
            // 检查缓存时间（存储在metadata中）
            const metadata = await env.FENGSHOWS_TOKEN.getWithMetadata('token');
            if (metadata && metadata.metadata && metadata.metadata.expires > Date.now()) {
                return cached;
            }
        }
    } else {
        // 如果不使用KV，使用内存缓存（仅对单个请求有效）
        // 生产环境建议使用KV
    }
    
    // 重新登录
    const url = 'https://m.fengshows.com/api/v3/mp/user/login';
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            code: prefix,
            keep_alive: false,
            password: pwd,
            phone: phone
        })
    });
    
    const result = await response.json();
    
    if (result && result.data && result.data.token) {
        const token = result.data.token;
        // 存储到KV，有效期30天
        if (env && env.FENGSHOWS_TOKEN) {
            await env.FENGSHOWS_TOKEN.put('token', token, {
                expirationTtl: 2592000, // 30天
                metadata: { expires: Date.now() + 2592000000 }
            });
        }
        return token;
    }
    
    return '';
}

/**
 * 获取播放地址
 */
async function getPlayUrl(channelId, quality, token, playseek = null) {
    let url;
    
    if (playseek) {
        // 回放
        const [start, end] = playseek.split('-');
        if (!start || !end) {
            return null;
        }
        
        // 时间转十六进制（毫秒时间戳）
        const startHex = (new Date(start).getTime()).toString(16);
        const endHex = (new Date(end).getTime()).toString(16);
        
        url = `https://m.fengshows.com/api/v3/hub/live/auth-url?` +
              `live_id=${channelId}&live_qa=${quality}&play_type=replay&` +
              `ps_time=${startHex}&pe_time=${endHex}`;
    } else {
        // 直播
        url = `https://api.fengshows.cn/hub/live/auth-url?live_qa=${quality.toLowerCase()}&live_id=${channelId}`;
    }
    
    // 请求头
    const headers = {
        'User-Agent': 'okhttp/3.14.9',
        'fengshows-client': 'app(android,5041401);Redmi;29'
    };
    
    if (token) {
        headers['Token'] = token;
    }
    
    try {
        const response = await fetch(url, { headers });
        const data = await response.json();
        return data.data && data.data.live_url ? data.data.live_url : null;
    } catch (e) {
        return null;
    }
}

/**
 * 处理请求
 */
async function handleRequest(request, env) {
    const url = new URL(request.url);
    
    // 获取参数
    let id = url.searchParams.get('id') || 'fhzw';
    const playseek = url.searchParams.get('playseek') || '';
    
    // 验证频道
    if (!channels[id]) {
        return new Response('无效的频道ID', { status: 400 });
    }
    
    const channelId = channels[id];
    
    // 获取token
    const token = await getToken(env, ACCOUNT_CONFIG.phone_prefix, ACCOUNT_CONFIG.phone, ACCOUNT_CONFIG.password);
    
    // 决定画质
    let quality = token ? 'FHD' : 'HD';  // 有token用FHD，无token用HD
    
    // 获取播放地址
    let playUrl = await getPlayUrl(channelId, quality, token, playseek);
    
    // 如果获取失败，尝试降级
    if (!playUrl && quality === 'FHD') {
        playUrl = await getPlayUrl(channelId, 'HD', token, playseek);
        if (playUrl) {
            quality = 'HD';
        }
    }
    
    if (!playUrl && !token) {
        playUrl = await getPlayUrl(channelId, 'SD', token, playseek);
    }
    
    if (playUrl) {
        // 302重定向
        return Response.redirect(playUrl, 302);
    } else {
        return new Response('获取播放地址失败', { status: 500 });
    }
}

// Worker入口
export default {
    async fetch(request, env, ctx) {
        return handleRequest(request, env);
    }
};