#include "ReShade.fxh"

uniform bool bEnableWall <
    ui_label = "Enable Wall & Texture";
> = false;

uniform int iViewMode <
    ui_type = "combo";
    ui_label = "Camera View";
    ui_items = "View 1\0View 2\0View 3\0View 4\0Custom\0";
> = 0;

uniform float fWallDistance <
    ui_label = "Wall Distance";
    ui_type = "drag";
    ui_min = 0.0;
    ui_max = 0.001;
    ui_step = 0.0000001;
> = 0.00002;

uniform float fTiltX <
    ui_category = "Advanced Settings";
    ui_label = "Horizontal Tilt";
    ui_type = "drag";
    ui_min = -0.01;
    ui_max = 0.01;
    ui_step = 0.0000001;
> = 0.0;

uniform float fTiltY <
    ui_category = "Advanced Settings";
    ui_label = "Vertical Tilt";
    ui_type = "drag";
    ui_min = -0.01;
    ui_max = 0.01;
    ui_step = 0.0000001;
> = 0.0;

uniform float3 cWallColor <
    ui_category = "Advanced Settings";
    ui_label = "Wall Color";
    ui_type = "color";
> = float3(1.0, 1.0, 1.0);

uniform float fWallOpacity <
    ui_category = "Advanced Settings";
    ui_label = "Wall Opacity";
    ui_type = "slider";
    ui_min = 0.0;
    ui_max = 1.0;
    ui_step = 0.01;
> = 0.5;

uniform float fCropTop <
    ui_category = "Advanced Settings";
    ui_label = "Crop Top";
    ui_type = "drag";
    ui_min = 0.0;
    ui_max = 1.0;
    ui_step = 0.01;
> = 0.0;

uniform float fPitch <
    ui_category = "Advanced Settings";
    ui_label = "Wall Pitch";
    ui_type = "drag";
    ui_min = -2.0;
    ui_max = 2.0;
    ui_step = 0.01;
> = 0.0;

uniform float fCropGradient <
    ui_category = "Advanced Settings";
    ui_label = "Crop Gradient";
    ui_type = "drag";
    ui_min = 0.0;
    ui_max = 1.0;
    ui_step = 0.001;
> = 0.0;

texture Offside_Tex < source = "Offside_Tex.png"; > { Width = 1920; Height = 1080; Format = RGBA8; };
sampler Offside_Sampler { Texture = Offside_Tex; };

float3 PS_DepthWall(in float4 position : SV_Position, in float2 texcoord : TEXCOORD) : SV_Target
{
    float3 originalColor = tex2D(ReShade::BackBuffer, texcoord).rgb;
    
    if (!bEnableWall)
    {
        return originalColor;
    }

    float currentTiltX = fTiltX;
    float currentTiltY = fTiltY;
    float3 currentColor = cWallColor;
    float currentOpacity = fWallOpacity;
    float currentCropTop = fCropTop;
    float currentPitch = fPitch;
    float currentGradient = fCropGradient;

    if (iViewMode == 0)
    {
        currentTiltX = -0.0001590;
        currentTiltY = -0.0000038;
        currentOpacity = 0.8;
        currentCropTop = 0.33;
        currentPitch = 0.22;
        currentGradient = 0.076;
        currentColor = float3(1.0, 1.0, 1.0);
    }
    else if (iViewMode == 1)
    {
        currentTiltX = 0.0001250;
        currentTiltY = -0.0000038;
        currentOpacity = 0.8;
        currentCropTop = 0.33;
        currentPitch = -0.11;
        currentGradient = 0.076;
        currentColor = float3(1.0, 1.0, 1.0);
    }
    else if (iViewMode == 2)
    {
        currentTiltX = 0.0001065;
        currentTiltY = -0.0000038;
        currentOpacity = 0.8;
        currentCropTop = 0.33;
        currentPitch = -0.15;
        currentGradient = 0.076;
        currentColor = float3(1.0, 1.0, 1.0);
    }
    else if (iViewMode == 3)
    {
        currentTiltX = -0.0001800;
        currentTiltY = -0.0000038;
        currentOpacity = 0.8;
        currentCropTop = 0.33;
        currentPitch = 0.22;
        currentGradient = 0.076;
        currentColor = float3(1.0, 1.0, 1.0);
    }

    float pixelDepth = ReShade::GetLinearizedDepth(texcoord);
    float cutLine = currentCropTop + (texcoord.x - 0.5) * currentPitch;
    float dynamicWallDistance = fWallDistance * (1.0 + (((texcoord.x - 0.5) * currentTiltX) + ((texcoord.y - 0.5) * currentTiltY)) / 0.00003);
    
    float3 finalColor = originalColor;

    if (pixelDepth < dynamicWallDistance)
    {
        float gradientFactor = currentGradient > 0.0 ? smoothstep(cutLine, cutLine + currentGradient, texcoord.y) : (texcoord.y >= cutLine ? 1.0 : 0.0);
        finalColor = lerp(originalColor, currentColor, currentOpacity * gradientFactor);
    }

    float4 layer = tex2D(Offside_Sampler, texcoord);
    finalColor = lerp(finalColor, layer.rgb, layer.a);

    return finalColor;
}

technique DepthWall 
{
    pass
    {
        VertexShader = PostProcessVS;
        PixelShader = PS_DepthWall;
    }
}