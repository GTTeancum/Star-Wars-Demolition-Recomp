using Silk.NET.OpenGL;
using RecompOne.Runtime.Config;
using RecompOne.Runtime.Dispatch;

namespace RecompOne.Runtime.Host.Window;

// Final host-only presentation pass. The source texture is always the completed
// PS1 framebuffer; this class cannot affect emulated VRAM or game state.
internal sealed class PresentationRenderer : IDisposable
{
    const string LoadingCardSuffix = "_loading_card_4x.ppm";

    const string UpscaleFs = """
        #version 330 core
        in vec2 vUv;
        uniform sampler2D uSource;
        uniform vec2 uSourceSize;
        uniform int uLinearFilter;
        uniform int uLoadingUiRestore;
        uniform sampler2D uLoadingCard;
        uniform int uLoadingCardOverlay;
        uniform vec4 uLoadingCardRect;
        uniform vec4 uLoadingCardSampleRect;
        // x,y bound the rows the engine draws the arena title into; z is the
        // channel difference above which a pixel counts as title rather than
        // art. Zero selects the fixed top strip instead of the key.
        uniform vec3 uLoadingCardTitleKey;
        uniform int uDeband;
        out vec4 oColor;

        vec3 sourcePixel(ivec2 p) {
            return texelFetch(
                uSource,
                clamp(p, ivec2(0), ivec2(uSourceSize) - 1),
                0).rgb;
        }

        vec3 sampleLinear(vec2 uv) {
            vec2 p = clamp(uv, vec2(0.0), vec2(1.0)) * uSourceSize - 0.5;
            ivec2 i0 = ivec2(floor(p));
            vec2 f = fract(p);
            ivec2 hi = ivec2(uSourceSize) - 1;
            i0 = clamp(i0, ivec2(0), hi);
            ivec2 i1 = min(i0 + 1, hi);
            vec3 a = mix(texelFetch(uSource, ivec2(i0.x, i0.y), 0).rgb,
                         texelFetch(uSource, ivec2(i1.x, i0.y), 0).rgb, f.x);
            vec3 b = mix(texelFetch(uSource, ivec2(i0.x, i1.y), 0).rgb,
                         texelFetch(uSource, ivec2(i1.x, i1.y), 0).rgb, f.x);
            return mix(a, b, f.y);
        }

        float hash12(vec2 p) {
            vec3 q = fract(vec3(p.xyx) * 0.1031);
            q += dot(q, q.yzx + 33.33);
            return fract((q.x + q.y) * q.z);
        }
        // A PlayStation texture with a small palette shows as plateaus: runs
        // of pixels holding one value, ending in a step of about eight
        // levels. Nothing spatial inside the texture can undo that, because
        // the neighbouring texels hold the same palette entry; the missing
        // levels have to be rebuilt in screen space, across the plateau.
        //
        // Measured on the Desert horizon: 76% of adjacent pixels in the sky
        // are exactly equal, and 60% on untextured far terrain, against 42%
        // on textured ground. Counting neighbours that match exactly is what
        // separates a plateau from detail - the local range does not, since
        // both sit at eight levels.
        vec3 deband(vec2 uv, vec3 center) {
            vec2 texel = 1.0 / uSourceSize;
            vec3 n = sourcePixel(ivec2(uv * uSourceSize) + ivec2( 0, -1));
            vec3 e = sourcePixel(ivec2(uv * uSourceSize) + ivec2( 1,  0));
            vec3 s = sourcePixel(ivec2(uv * uSourceSize) + ivec2( 0,  1));
            vec3 w = sourcePixel(ivec2(uv * uSourceSize) + ivec2(-1,  0));
            float tol = 1.5 / 255.0;
            float matches =
                (all(lessThan(abs(n - center), vec3(tol))) ? 1.0 : 0.0) +
                (all(lessThan(abs(e - center), vec3(tol))) ? 1.0 : 0.0) +
                (all(lessThan(abs(s - center), vec3(tol))) ? 1.0 : 0.0) +
                (all(lessThan(abs(w - center), vec3(tol))) ? 1.0 : 0.0);
            float plateau = smoothstep(1.5, 3.5, matches);
            if (plateau <= 0.001)
                return center;
            // Reach past the plateau. The sky is 256 texels across the
            // frame, so one texel covers about four source pixels and a
            // plateau two or three of them; six pixels spans one. The angle
            // is per-pixel so the taps never form a visible pattern.
            float angle = hash12(gl_FragCoord.xy) * 6.2831853;
            vec2 step1 = vec2(cos(angle), sin(angle)) * texel * 6.0;
            vec2 step2 = vec2(-step1.y, step1.x);
            vec3 sum = center;
            float weight = 1.0;
            for (int i = 0; i < 4; i++) {
                vec2 offset = i == 0 ? step1 : i == 1 ? -step1
                            : i == 2 ? step2 : -step2;
                vec3 tap = sampleLinear(uv + offset);
                vec3 d = abs(tap - center);
                // One band step is about eight levels; a real edge is far
                // larger, so taps across an edge contribute nothing.
                float w = 1.0 - smoothstep(
                    10.0 / 255.0, 16.0 / 255.0,
                    max(d.r, max(d.g, d.b)));
                sum += tap * w;
                weight += w;
            }
            vec3 smoothed = sum / weight;
            // A little noise below one level keeps whatever contour survives
            // from re-forming when the result is quantised for display.
            float dither = (hash12(gl_FragCoord.yx) - 0.5) / 255.0;
            return mix(center, smoothed + dither, plateau);
        }
        void main() {
            ivec2 size = ivec2(uSourceSize);
            ivec2 p = clamp(ivec2(vUv * uSourceSize), ivec2(0), size - 1);
            vec3 center = uLinearFilter != 0
                ? sampleLinear(vUv)
                : sourcePixel(p);
            if (uDeband != 0)
                center = deband(vUv, center);
            bool loadingCardPixel = false;
            if (uLoadingCardOverlay != 0) {
                vec2 innerUv =
                    (vUv - uLoadingCardRect.xy) / uLoadingCardRect.zw;
                if (innerUv.x >= 0.0 && innerUv.x <= 1.0 &&
                    innerUv.y >= 0.0 && innerUv.y <= 1.0) {
                    vec2 cardUv = uLoadingCardSampleRect.xy +
                        innerUv * uLoadingCardSampleRect.zw;
                    vec3 card = texture(uLoadingCard, cardUv).rgb;
                    // The native title is drawn after the card and remains
                    // authoritative. Where the card reproduces the original
                    // art exactly, the pixels that disagree with it are the
                    // title and its outline, so keying on that disagreement
                    // preserves the glyphs without also holding back a strip
                    // of original art around them.
                    bool preserveTitle;
                    if (uLoadingCardTitleKey.z > 0.0) {
                        vec3 delta = abs(center - card);
                        preserveTitle =
                            vUv.y >= uLoadingCardTitleKey.x &&
                            vUv.y <= uLoadingCardTitleKey.y &&
                            max(delta.r, max(delta.g, delta.b)) >
                                uLoadingCardTitleKey.z;
                    } else {
                        preserveTitle = vUv.y < 0.16;
                    }
                    if (!preserveTitle) {
                        center = card;
                        loadingCardPixel = true;
                    }
                }
            }
            if (uLoadingUiRestore != 0 && !loadingCardPixel) {
                vec2 texel = 1.0 / uSourceSize;
                vec3 n  = sampleLinear(vUv + vec2( 0.0, -texel.y));
                vec3 e  = sampleLinear(vUv + vec2( texel.x,  0.0));
                vec3 s  = sampleLinear(vUv + vec2( 0.0,  texel.y));
                vec3 w  = sampleLinear(vUv + vec2(-texel.x,  0.0));
                vec3 ne = sampleLinear(vUv + vec2( texel.x, -texel.y));
                vec3 se = sampleLinear(vUv + vec2( texel.x,  texel.y));
                vec3 sw = sampleLinear(vUv + vec2(-texel.x,  texel.y));
                vec3 nw = sampleLinear(vUv + vec2(-texel.x, -texel.y));

                vec3 lo = min(center, min(min(n, e), min(s, w)));
                lo = min(lo, min(min(ne, se), min(sw, nw)));
                vec3 hi = max(center, max(max(n, e), max(s, w)));
                hi = max(hi, max(max(ne, se), max(sw, nw)));
                float localRange = max(
                    hi.r - lo.r,
                    max(hi.g - lo.g, hi.b - lo.b));

                vec3 average =
                    (center * 4.0 + n + e + s + w +
                     (ne + se + sw + nw) * 0.5) / 10.0;
                float restore = 1.0 - smoothstep(0.09, 0.32, localRange);
                vec3 denoised = mix(center, average, restore * 0.65);
                vec3 blur = (denoised * 4.0 + n + e + s + w) / 8.0;
                vec3 sharpened = denoised + (denoised - blur) *
                    (0.45 * restore);
                oColor = vec4(clamp(sharpened, lo - 0.025, hi + 0.025), 1.0);
                return;
            }
            oColor = vec4(center, 1.0);
        }
        """;

    const string FxaaFs = """
        #version 330 core
        in vec2 vUv;
        uniform sampler2D uSource;
        uniform vec2 uSourceSize;
        uniform vec2 uInvResolution;
        out vec4 oColor;

        vec3 sampleLinear(vec2 uv) {
            vec2 p = clamp(uv, vec2(0.0), vec2(1.0)) * uSourceSize - 0.5;
            ivec2 i0 = ivec2(floor(p));
            vec2 f = fract(p);
            ivec2 hi = ivec2(uSourceSize) - 1;
            i0 = clamp(i0, ivec2(0), hi);
            ivec2 i1 = min(i0 + 1, hi);
            vec3 a = mix(texelFetch(uSource, ivec2(i0.x, i0.y), 0).rgb,
                         texelFetch(uSource, ivec2(i1.x, i0.y), 0).rgb, f.x);
            vec3 b = mix(texelFetch(uSource, ivec2(i0.x, i1.y), 0).rgb,
                         texelFetch(uSource, ivec2(i1.x, i1.y), 0).rgb, f.x);
            return mix(a, b, f.y);
        }

        float luma(vec3 rgb) { return dot(rgb, vec3(0.299, 0.587, 0.114)); }

        void main() {
            vec3 nw = sampleLinear(vUv + vec2(-1.0, -1.0) * uInvResolution);
            vec3 ne = sampleLinear(vUv + vec2( 1.0, -1.0) * uInvResolution);
            vec3 sw = sampleLinear(vUv + vec2(-1.0,  1.0) * uInvResolution);
            vec3 se = sampleLinear(vUv + vec2( 1.0,  1.0) * uInvResolution);
            vec3 m  = sampleLinear(vUv);
            vec3 n  = sampleLinear(vUv + vec2( 0.0, -1.0) * uInvResolution);
            vec3 e  = sampleLinear(vUv + vec2( 1.0,  0.0) * uInvResolution);
            vec3 s  = sampleLinear(vUv + vec2( 0.0,  1.0) * uInvResolution);
            vec3 w  = sampleLinear(vUv + vec2(-1.0,  0.0) * uInvResolution);

            float lumaNW = luma(nw), lumaNE = luma(ne);
            float lumaSW = luma(sw), lumaSE = luma(se), lumaM = luma(m);
            float lumaMin = min(lumaM, min(min(lumaNW, lumaNE), min(lumaSW, lumaSE)));
            float lumaMax = max(lumaM, max(max(lumaNW, lumaNE), max(lumaSW, lumaSE)));

            // Preserve isolated one-pixel extrema such as HUD glyph strokes,
            // targeting reticles and gauge ticks. A silhouette has at least
            // one same-side neighbour and continues through normal FXAA.
            float lumaN = luma(n), lumaE = luma(e);
            float lumaS = luma(s), lumaW = luma(w);
            float oppositeMax = max(max(lumaN, lumaS), max(lumaE, lumaW));
            float oppositeMin = min(min(lumaN, lumaS), min(lumaE, lumaW));
            bool centerExtreme =
                lumaM > oppositeMax + 0.10 ||
                lumaM < oppositeMin - 0.10;
            bool thinStroke =
                (abs(lumaM - lumaN) > 0.12 &&
                 abs(lumaM - lumaS) > 0.12 &&
                 abs(lumaN - lumaS) < 0.10) ||
                (abs(lumaM - lumaE) > 0.12 &&
                 abs(lumaM - lumaW) > 0.12 &&
                 abs(lumaE - lumaW) < 0.10);
            if (centerExtreme && thinStroke) {
                oColor = vec4(m, 1.0);
                return;
            }

            vec2 dir;
            dir.x = -((lumaNW + lumaNE) - (lumaSW + lumaSE));
            dir.y =  ((lumaNW + lumaSW) - (lumaNE + lumaSE));
            float reduce = max((lumaNW + lumaNE + lumaSW + lumaSE) * (0.25 / 8.0), 1.0 / 128.0);
            float reciprocal = 1.0 / (min(abs(dir.x), abs(dir.y)) + reduce);
            dir = clamp(dir * reciprocal, vec2(-8.0), vec2(8.0)) * uInvResolution;

            vec3 a = 0.5 * (sampleLinear(vUv + dir * (1.0 / 3.0 - 0.5)) +
                            sampleLinear(vUv + dir * (2.0 / 3.0 - 0.5)));
            vec3 b = a * 0.5 + 0.25 * (sampleLinear(vUv + dir * -0.5) +
                                      sampleLinear(vUv + dir *  0.5));
            float lumaB = luma(b);
            oColor = vec4((lumaB < lumaMin || lumaB > lumaMax) ? a : b, 1.0);
        }
        """;

    readonly GL _gl;
    uint _vao, _vbo, _upscaleProgram, _fxaaProgram;
    uint _upscaleTexture, _fxaaTexture, _upscaleFbo, _fxaaFbo;
    readonly Dictionary<string, uint> _loadingCardTextures =
        new(StringComparer.OrdinalIgnoreCase);
    readonly Dictionary<string, string> _loadingCardPaths =
        new(StringComparer.OrdinalIgnoreCase);
    readonly Dictionary<string, (int Width, int Height)> _loadingCardSizes =
        new(StringComparer.OrdinalIgnoreCase);
    string? _lastLoadingCardArena;
    // Counts upscale passes so a capture can be aimed at the loading window,
    // which is otherwise invisible in the log between two arena overlays.
    int _upscalePass;
    bool _loadingCardWasActive;
    int _width, _height;
    int _lastSourceWidth, _lastSourceHeight, _lastOutputWidth, _lastOutputHeight;
    bool _lastFxaa;
    int _upscaleSourceSize;
    int _upscaleLinearFilter, _upscaleLoadingUiRestore;
    int _upscaleLoadingCardOverlay, _upscaleLoadingCardRect;
    int _upscaleLoadingCardSampleRect;
    int _upscaleLoadingCardTitleKey;
    int _upscaleDeband;
    int _fxaaSourceSize, _fxaaInvResolution;

    public bool Ready { get; private set; }

    public PresentationRenderer(GL gl) => _gl = gl;

    public unsafe void Initialize()
    {
        _upscaleProgram = Enhanced.GlShaders.Build(
            _gl,
            Enhanced.GlShaders.FullscreenVs,
            UpscaleFs,
            "presentation-upscale");
        _fxaaProgram = Enhanced.GlShaders.Build(
            _gl,
            Enhanced.GlShaders.FullscreenVs,
            FxaaFs,
            "presentation-fxaa");
        if (_upscaleProgram == 0 || _fxaaProgram == 0) return;

        _gl.UseProgram(_upscaleProgram);
        _gl.Uniform1(_gl.GetUniformLocation(_upscaleProgram, "uSource"), 0);
        _gl.Uniform1(_gl.GetUniformLocation(_upscaleProgram, "uLoadingCard"), 1);
        _upscaleSourceSize = _gl.GetUniformLocation(_upscaleProgram, "uSourceSize");
        _upscaleLinearFilter =
            _gl.GetUniformLocation(_upscaleProgram, "uLinearFilter");
        _upscaleLoadingUiRestore =
            _gl.GetUniformLocation(_upscaleProgram, "uLoadingUiRestore");
        _upscaleLoadingCardOverlay =
            _gl.GetUniformLocation(_upscaleProgram, "uLoadingCardOverlay");
        _upscaleLoadingCardRect =
            _gl.GetUniformLocation(_upscaleProgram, "uLoadingCardRect");
        _upscaleLoadingCardSampleRect =
            _gl.GetUniformLocation(_upscaleProgram, "uLoadingCardSampleRect");
        _upscaleLoadingCardTitleKey =
            _gl.GetUniformLocation(_upscaleProgram, "uLoadingCardTitleKey");
        _upscaleDeband = _gl.GetUniformLocation(_upscaleProgram, "uDeband");
        _gl.UseProgram(_fxaaProgram);
        _gl.Uniform1(_gl.GetUniformLocation(_fxaaProgram, "uSource"), 0);
        _fxaaSourceSize = _gl.GetUniformLocation(_fxaaProgram, "uSourceSize");
        _fxaaInvResolution = _gl.GetUniformLocation(_fxaaProgram, "uInvResolution");

        _vao = _gl.GenVertexArray();
        _vbo = _gl.GenBuffer();
        _gl.BindVertexArray(_vao);
        _gl.BindBuffer(BufferTargetARB.ArrayBuffer, _vbo);
        float[] quad = [-1f, -1f, 1f, -1f, -1f, 1f, 1f, 1f];
        fixed (float* vertices = quad)
            _gl.BufferData(BufferTargetARB.ArrayBuffer, (nuint)(quad.Length * sizeof(float)), vertices, BufferUsageARB.StaticDraw);
        _gl.EnableVertexAttribArray(0);
        _gl.VertexAttribPointer(0, 2, VertexAttribPointerType.Float, false, 2 * sizeof(float), (void*)0);

        (_upscaleTexture, _upscaleFbo) = CreateTarget();
        (_fxaaTexture, _fxaaFbo) = CreateTarget();
        LoadLoadingCardOverlays();
        EnsureSize(1, 1);
        _gl.BindFramebuffer(FramebufferTarget.Framebuffer, 0);
        Ready = true;
    }

    (uint texture, uint fbo) CreateTarget()
    {
        uint texture = _gl.GenTexture();
        _gl.BindTexture(TextureTarget.Texture2D, texture);
        _gl.TexParameter(TextureTarget.Texture2D, TextureParameterName.TextureMinFilter, (int)GLEnum.Nearest);
        _gl.TexParameter(TextureTarget.Texture2D, TextureParameterName.TextureMagFilter, (int)GLEnum.Nearest);
        _gl.TexParameter(TextureTarget.Texture2D, TextureParameterName.TextureWrapS, (int)GLEnum.ClampToEdge);
        _gl.TexParameter(TextureTarget.Texture2D, TextureParameterName.TextureWrapT, (int)GLEnum.ClampToEdge);
        uint fbo = _gl.GenFramebuffer();
        _gl.BindFramebuffer(FramebufferTarget.Framebuffer, fbo);
        _gl.FramebufferTexture2D(FramebufferTarget.Framebuffer, FramebufferAttachment.ColorAttachment0,
            TextureTarget.Texture2D, texture, 0);
        return (texture, fbo);
    }

    unsafe void EnsureSize(int width, int height)
    {
        if (width == _width && height == _height) return;
        foreach (uint texture in new[] { _upscaleTexture, _fxaaTexture })
        {
            _gl.BindTexture(TextureTarget.Texture2D, texture);
            _gl.TexImage2D(TextureTarget.Texture2D, 0, InternalFormat.Rgba8, (uint)width, (uint)height, 0,
                PixelFormat.Rgba, PixelType.UnsignedByte, null);
        }
        _width = width;
        _height = height;
    }

    public uint Render(uint sourceTexture, int sourceWidth, int sourceHeight,
        int outputWidth, int outputHeight, bool fxaa, string? captureLabel = null)
    {
        if (!Ready || sourceTexture == 0 || sourceWidth <= 0 || sourceHeight <= 0)
            return sourceTexture;

        outputWidth = Math.Clamp(outputWidth, 1, 8192);
        outputHeight = Math.Clamp(outputHeight, 1, 8192);
        EnsureSize(outputWidth, outputHeight);
        if (sourceWidth != _lastSourceWidth || sourceHeight != _lastSourceHeight ||
            outputWidth != _lastOutputWidth || outputHeight != _lastOutputHeight || fxaa != _lastFxaa)
        {
            Console.WriteLine($"[Host] presentation source={sourceWidth}x{sourceHeight} output={outputWidth}x{outputHeight} aa={(fxaa ? "FXAA" : "Off")}");
            _lastSourceWidth = sourceWidth;
            _lastSourceHeight = sourceHeight;
            _lastOutputWidth = outputWidth;
            _lastOutputHeight = outputHeight;
            _lastFxaa = fxaa;
        }

        PreparePass(_upscaleFbo, _upscaleProgram, sourceTexture);
        _gl.Uniform2(_upscaleSourceSize, (float)sourceWidth, sourceHeight);
        bool isV82 = Runtime.GameTitle.Contains(
            "2nd Offense", StringComparison.Ordinal);
        bool isDemolition = Runtime.GameTitle.Contains(
            "Demolition", StringComparison.Ordinal);
        bool offGameplayV82Ui =
            ConfigManager.View.HighResolutionTextures &&
            isV82 &&
            RecompOne.Runtime.Hle.GpuHle.Active &&
            !RecompOne.Runtime.Hle.GpuHle.GameplayActive;
        // The presentation source is the native 320x240 canvas multiplied by
        // the selected internal scale (and optionally widened). Loading-card
        // replacement is normalized in UV space, so requiring a particular
        // scale such as 4x incorrectly disables it at the Enhanced 3x preset.
        bool validV82PresentationSource =
            sourceWidth >= 320 && sourceHeight >= 240;
        // Demolition's loading screen belongs to the SHELL_LOAD overlay and
        // runs entirely before the arena's VRAM layout is installed, so the
        // gameplay tick is still meaningless there; keying on the overlay
        // covers the whole screen rather than its single closing frame.
        // SHELL_LOAD is not unloaded when the match begins - it stays resident
        // until the shell reclaims its memory - so the gameplay flag, which
        // the VRAM reset raises, is what closes the window.
        bool demolitionLoadingScreen =
            isDemolition &&
            !RecompOne.Runtime.Hle.GpuHle.GameplayActive &&
            Array.Exists(
                Dispatcher.ActiveNames,
                name => name.Equals(
                    "SHELL_LOAD", StringComparison.OrdinalIgnoreCase));
        bool preTickLoadingCard =
            ConfigManager.View.HighResolutionTextures &&
            RecompOne.Runtime.Hle.GpuHle.Active &&
            validV82PresentationSource &&
            (demolitionLoadingScreen ||
             (isV82 &&
              RecompOne.Runtime.Hle.GpuHle.GameplayActive &&
              RecompOne.Runtime.Hle.GpuHle.DebugGameplayTick == 0));
        bool frontendPresentation =
            RecompOne.Runtime.Hle.GpuHle.Active &&
            !RecompOne.Runtime.Hle.GpuHle.GameplayActive &&
            (isV82 || isDemolition);
        bool uiPresentation = frontendPresentation || preTickLoadingCard;
        bool loadingUiSource =
            (offGameplayV82Ui || preTickLoadingCard) &&
            validV82PresentationSource;
        _gl.Uniform1(_upscaleLinearFilter, 0);
        _gl.Uniform1(
            _upscaleDeband, ConfigManager.View.GradientSmoothing ? 1 : 0);
        _gl.Uniform1(_upscaleLoadingUiRestore, loadingUiSource ? 1 : 0);
        string? importedArena =
            RecompOne.Runtime.Sdk.V82ArenaRegistry.SelectedOverlayName;
        string? latestRetailArena = Dispatcher.LatestLevelName;
        string? loadingCardArena =
            importedArena != null &&
            _loadingCardTextures.ContainsKey(importedArena)
                ? importedArena
                : latestRetailArena != null &&
                  _loadingCardTextures.ContainsKey(latestRetailArena)
                    ? latestRetailArena
                    : Dispatcher.ActiveNames.LastOrDefault(
                        name => _loadingCardTextures.ContainsKey(name));
        uint loadingCardTexture = loadingCardArena == null
            ? 0
            : _loadingCardTextures[loadingCardArena];
        (int Width, int Height) loadingCardSize = loadingCardArena == null
            ? (1280, 384)
            : _loadingCardSizes[loadingCardArena];
        bool loadingCardOverlay =
            preTickLoadingCard && loadingCardTexture != 0;
        _gl.Uniform1(
            _upscaleLoadingCardOverlay,
            loadingCardOverlay ? 1 : 0);
        if (isDemolition)
        {
            // The loading picture occupies native rows 16..127 of the 240-line
            // canvas at full width, and the Dreamcast card is that same band at
            // 2x with no padding of its own, so it maps one to one.
            _gl.Uniform4(
                _upscaleLoadingCardRect, 0f, 16f / 240f, 1f, 112f / 240f);
            _gl.Uniform4(_upscaleLoadingCardSampleRect, 0f, 0f, 1f, 1f);
            // The arena title sits between native rows 21 and 49. A channel
            // difference of 0.35 separates its glyphs, which disagree with the
            // card by 0.83 at the ninetieth percentile, from the art beneath,
            // which agrees to within 0.21 at the ninety-ninth.
            _gl.Uniform3(_upscaleLoadingCardTitleKey, 0.088f, 0.202f, 0.35f);
        }
        else
        {
            float loadingCardRectHeight =
                loadingCardSize.Height == 448 ? 288f : 240f;
            _gl.Uniform4(
                _upscaleLoadingCardRect,
                0f,
                (210f - loadingCardRectHeight * 0.5f) / 720f,
                1f,
                loadingCardRectHeight / 720f);
            _gl.Uniform4(
                _upscaleLoadingCardSampleRect,
                0f,
                32f / loadingCardSize.Height,
                1f,
                (loadingCardSize.Height - 64f) / loadingCardSize.Height);
            _gl.Uniform3(_upscaleLoadingCardTitleKey, 0f, 0f, 0f);
        }
        if (loadingCardOverlay)
        {
            if (!loadingCardArena!.Equals(
                    _lastLoadingCardArena,
                    StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine(
                    $"[TexturePack] selected loading card overlay " +
                    $"arena={loadingCardArena} pass={_upscalePass}: " +
                    _loadingCardPaths[loadingCardArena]);
                _lastLoadingCardArena = loadingCardArena;
            }
            _gl.ActiveTexture(TextureUnit.Texture1);
            _gl.BindTexture(TextureTarget.Texture2D, loadingCardTexture);
            _gl.ActiveTexture(TextureUnit.Texture0);
        }
        else
        {
            // A later match may deliberately reuse the same arena. Clear the
            // diagnostic latch between loading transitions so the smoke
            // harness can prove that the HD card was selected on every visit.
            _lastLoadingCardArena = null;
            if (_loadingCardWasActive)
                Console.WriteLine(
                    $"[TexturePack] loading card overlay ended pass={_upscalePass}");
        }
        _loadingCardWasActive = loadingCardOverlay;
        _upscalePass++;
        _gl.DrawArrays(PrimitiveType.TriangleStrip, 0, 4);

        uint finalTexture = _upscaleTexture;
        uint finalFbo = _upscaleFbo;
        bool finalFxaa = fxaa && !uiPresentation;
        if (finalFxaa)
        {
            PreparePass(_fxaaFbo, _fxaaProgram, _upscaleTexture);
            _gl.Uniform2(_fxaaSourceSize, (float)outputWidth, outputHeight);
            _gl.Uniform2(_fxaaInvResolution, 1f / outputWidth, 1f / outputHeight);
            _gl.DrawArrays(PrimitiveType.TriangleStrip, 0, 4);
            finalTexture = _fxaaTexture;
            finalFbo = _fxaaFbo;
        }

        if (!string.IsNullOrEmpty(captureLabel))
            CapturePpm(finalFbo, outputWidth, outputHeight, captureLabel, finalFxaa);

        _gl.BindFramebuffer(FramebufferTarget.Framebuffer, 0);
        return finalTexture;
    }

    void PreparePass(uint fbo, uint program, uint sourceTexture)
    {
        _gl.BindFramebuffer(FramebufferTarget.Framebuffer, fbo);
        _gl.Viewport(0, 0, (uint)_width, (uint)_height);
        _gl.Disable(EnableCap.DepthTest);
        _gl.Disable(EnableCap.Blend);
        _gl.Disable(EnableCap.ScissorTest);
        _gl.Disable(EnableCap.CullFace);
        _gl.UseProgram(program);
        _gl.BindVertexArray(_vao);
        _gl.ActiveTexture(TextureUnit.Texture0);
        _gl.BindTexture(TextureTarget.Texture2D, sourceTexture);
    }

    void LoadLoadingCardOverlays()
    {
        var directories = new SortedSet<string>(
            StringComparer.OrdinalIgnoreCase);
        string? overrideDirectory =
            Environment.GetEnvironmentVariable("RECOMPONE_LOADING_CARD_DIR");
        if (!string.IsNullOrWhiteSpace(overrideDirectory))
            directories.Add(Path.GetFullPath(overrideDirectory));
        else
            directories.Add(Path.Combine(
                Runtime.ModsDirectory,
                "enhanced_textures_2x",
                "loading_cards"));

        if (Directory.Exists(Runtime.ModsDirectory))
        {
            foreach (string modDirectory in Directory.EnumerateDirectories(
                         Runtime.ModsDirectory))
                directories.Add(Path.Combine(modDirectory, "loading_cards"));
        }

        foreach (string directory in directories)
            if (Directory.Exists(directory))
                LoadLoadingCardDirectory(directory);

        Console.WriteLine(
            $"[TexturePack] loaded {_loadingCardTextures.Count} " +
            "loading card overlays");
    }

    void LoadLoadingCardDirectory(string directory)
    {
        foreach (string path in Directory.EnumerateFiles(
                     directory, $"*{LoadingCardSuffix}"))
        {
            string fileName = Path.GetFileName(path);
            string stem = fileName[..^LoadingCardSuffix.Length];
            LoadLoadingCardOverlay(
                $"LEVELS_{stem.ToUpperInvariant()}", path);
        }
    }

    void LoadLoadingCardOverlay(string arena, string path)
    {
        try
        {
            (int width, int height, byte[] rgb) = ReadP6Ppm(path);
            if (width != 1280 || (height != 384 && height != 448))
                throw new InvalidDataException(
                    $"expected 1280x384 or 1280x448, found {width}x{height}");
            uint texture = _gl.GenTexture();
            _gl.BindTexture(TextureTarget.Texture2D, texture);
            _gl.TexParameter(
                TextureTarget.Texture2D,
                TextureParameterName.TextureMinFilter,
                (int)GLEnum.Linear);
            _gl.TexParameter(
                TextureTarget.Texture2D,
                TextureParameterName.TextureMagFilter,
                (int)GLEnum.Linear);
            _gl.TexParameter(
                TextureTarget.Texture2D,
                TextureParameterName.TextureWrapS,
                (int)GLEnum.ClampToEdge);
            _gl.TexParameter(
                TextureTarget.Texture2D,
                TextureParameterName.TextureWrapT,
                (int)GLEnum.ClampToEdge);
            _gl.PixelStore(PixelStoreParameter.UnpackAlignment, 1);
            _gl.TexImage2D<byte>(
                TextureTarget.Texture2D,
                0,
                InternalFormat.Rgb8,
                (uint)width,
                (uint)height,
                0,
                PixelFormat.Rgb,
                PixelType.UnsignedByte,
                rgb);
            if (_loadingCardTextures.Remove(
                    arena, out uint replacedTexture))
                _gl.DeleteTexture(replacedTexture);
            _loadingCardTextures[arena] = texture;
            _loadingCardPaths[arena] = Path.GetFullPath(path);
            _loadingCardSizes[arena] = (width, height);
            Console.WriteLine(
                $"[TexturePack] loaded loading card overlay arena={arena} " +
                $"{width}x{height}: {path}");
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(
                $"[TexturePack] ignored loading card overlay arena={arena} " +
                $"{path}: {ex.Message}");
        }
    }

    static (int Width, int Height, byte[] Rgb) ReadP6Ppm(string path)
    {
        byte[] data = File.ReadAllBytes(path);
        int cursor = 0;
        string magic = NextPpmToken(data, ref cursor);
        if (magic != "P6")
            throw new InvalidDataException("not a binary PPM");
        int width = int.Parse(NextPpmToken(data, ref cursor));
        int height = int.Parse(NextPpmToken(data, ref cursor));
        int max = int.Parse(NextPpmToken(data, ref cursor));
        if (width <= 0 || height <= 0 || max != 255)
            throw new InvalidDataException("unsupported PPM header");
        if (cursor >= data.Length || data[cursor] > 32)
            throw new InvalidDataException("missing PPM header separator");
        cursor += cursor + 1 < data.Length &&
            data[cursor] == '\r' && data[cursor + 1] == '\n' ? 2 : 1;
        int bytes = checked(width * height * 3);
        if (data.Length - cursor < bytes)
            throw new InvalidDataException("short PPM payload");
        byte[] rgb = new byte[bytes];
        System.Buffer.BlockCopy(data, cursor, rgb, 0, bytes);
        return (width, height, rgb);
    }

    static string NextPpmToken(byte[] data, ref int cursor)
    {
        while (cursor < data.Length)
        {
            byte b = data[cursor];
            if (b == '#')
            {
                while (cursor < data.Length && data[cursor] != '\n')
                    cursor++;
                continue;
            }
            if (b > 32) break;
            cursor++;
        }
        int start = cursor;
        while (cursor < data.Length && data[cursor] > 32) cursor++;
        if (start == cursor)
            throw new InvalidDataException("truncated PPM header");
        return System.Text.Encoding.ASCII.GetString(
            data, start, cursor - start);
    }

    void CapturePpm(uint fbo, int width, int height, string label, bool fxaa)
    {
        // The source upload stores its first (top) scanline at texture row zero.
        // The two fullscreen passes preserve that convention, so GL readback is
        // already in the top-to-bottom order expected by PPM.
        byte[] pixels = new byte[width * height * 3];
        _gl.BindFramebuffer(FramebufferTarget.ReadFramebuffer, fbo);
        _gl.PixelStore(PixelStoreParameter.PackAlignment, 1);
        _gl.ReadPixels(0, 0, (uint)width, (uint)height, PixelFormat.Rgb, PixelType.UnsignedByte, pixels.AsSpan());

        string mode = fxaa ? "fxaa" : "off";
        string path = $"recompone_present_{label}_{width}x{height}_{mode}.ppm";
        string? captureDirectory =
            Environment.GetEnvironmentVariable("RECOMPONE_CAPTURE_DIR");
        if (!string.IsNullOrWhiteSpace(captureDirectory))
        {
            captureDirectory = Path.GetFullPath(captureDirectory);
            Directory.CreateDirectory(captureDirectory);
            path = Path.Combine(captureDirectory, path);
        }
        using var output = File.Create(path);
        byte[] header = System.Text.Encoding.ASCII.GetBytes($"P6\n{width} {height}\n255\n");
        output.Write(header);
        output.Write(pixels);
        Console.WriteLine($"[Host] captured presentation '{label}' at {width}x{height} aa={mode} to {path}");
    }

    public void Dispose()
    {
        if (_vbo != 0) _gl.DeleteBuffer(_vbo);
        if (_vao != 0) _gl.DeleteVertexArray(_vao);
        if (_upscaleProgram != 0) _gl.DeleteProgram(_upscaleProgram);
        if (_fxaaProgram != 0) _gl.DeleteProgram(_fxaaProgram);
        if (_upscaleTexture != 0) _gl.DeleteTexture(_upscaleTexture);
        if (_fxaaTexture != 0) _gl.DeleteTexture(_fxaaTexture);
        foreach (uint texture in _loadingCardTextures.Values)
            _gl.DeleteTexture(texture);
        if (_upscaleFbo != 0) _gl.DeleteFramebuffer(_upscaleFbo);
        if (_fxaaFbo != 0) _gl.DeleteFramebuffer(_fxaaFbo);
    }
}
