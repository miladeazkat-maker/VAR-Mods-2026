#include "ReShade.fxh"

#ifndef OVERLAY_SOURCE
#define OVERLAY_SOURCE "Offside_Tex.png"
#endif

uniform bool uShowPlane < 
    ui_label = "Enable Plane"; 
> = true;

uniform int uCameraView < 
    ui_type = "combo"; 
    ui_items = "View 1\0View 2\0View 3\0View 4\0Custom\0";
    ui_label = "Select View"; 
> = 0;

uniform float uTargetDepth < 
    ui_type = "slider";
    ui_label = "Plane Position"; 
    ui_min = 0.001; ui_max = 0.1; ui_step = 0.0001; 
> = 0.5;

uniform bool Enable_Overlay <
    ui_label = "Enable Offside Overlay";
> = false;

uniform float uRotationX < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = -10.0; ui_max = 10.0; ui_step = 0.001; > = 0.0;
uniform float uRotationY < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = -10.0; ui_max = 10.0; ui_step = 0.001; > = 0.0;
uniform float uWallTop < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = -5.0; ui_max = 5.0; ui_step = 0.01; > = -0.5;
uniform float uFadeTop < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = 0.0; ui_max = 5.0; ui_step = 0.005; > = 0.5;
uniform float uWallBottom < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = -5.0; ui_max = 5.0; ui_step = 0.01; > = 1.0;
uniform float uHorizonLevel < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = -2.0; ui_max = 2.0; ui_step = 0.001; > = 0.0;
uniform float uCenterOffsetX < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = -0.5; ui_max = 0.5; ui_step = 0.001; > = 0.0;
uniform float uCenterOffsetY < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = -2.0; ui_max = 2.0; ui_step = 0.001; > = 0.0;
uniform float uDriftX < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = -1.0; ui_max = 1.0; ui_step = 0.001; > = 0.0;
uniform float3 uPlaneColor < ui_category = "Advanced Settings"; ui_type = "color"; > = float3(1.0, 0.0, 0.0);
uniform float uOpacity < ui_category = "Advanced Settings"; ui_type = "slider"; ui_min = 0.0; ui_max = 1.0; ui_step = 0.01; > = 0.5;

texture Offside_Texture < source = OVERLAY_SOURCE; > {
    Width  = BUFFER_WIDTH;
    Height = BUFFER_HEIGHT;
    Format = RGBA8;
};

sampler Offside_Sampler {
    Texture  = Offside_Texture;
    AddressU = BORDER;
    AddressV = BORDER;
};

void PS_CombinedOffside(in float4 position : SV_Position, in float2 texcoord : TEXCOORD, out float4 color : SV_Target)
{
    float rotX = uRotationX;
    float rotY = uRotationY;
    float wTop = uWallTop;
    float fTop = uFadeTop;
    float wBot = uWallBottom;
    float hLvl = uHorizonLevel;
    float cOffX = uCenterOffsetX;
    float cOffY = uCenterOffsetY;
    float dX = uDriftX;
    float3 pCol = uPlaneColor;
    float opac = uOpacity;

    if (uCameraView == 0) {
        rotX = -0.022; rotY = -1.351;
        wTop = -0.01; fTop = 0.01; wBot = 1.0; hLvl = -0.102; cOffX = 0.003; cOffY = 0.0;
        dX = 0.320; pCol = float3(1.0, 1.0, 1.0); opac = 0.85;
    } else if (uCameraView == 1) {
        rotX = 0.037; rotY = 1.926;
        wTop = -0.01; fTop = 0.01; wBot = 1.0; hLvl = -0.102; cOffX = 0.029; cOffY = 0.0;
        dX = 0.320; pCol = float3(1.0, 1.0, 1.0); opac = 0.85;
    } else if (uCameraView == 2) {
        rotX = 0.037; rotY = 1.825;
        wTop = -0.01; fTop = 0.01; wBot = 1.0; hLvl = -0.102; cOffX = 0.003; cOffY = 0.0;
        dX = 0.320; pCol = float3(1.0, 1.0, 1.0); opac = 0.85;
    } else if (uCameraView == 3) {
        rotX = -0.022; rotY = -4.283;
        wTop = -0.01; fTop = 0.01; wBot = 1.0; hLvl = -0.102; cOffX = 0.030; cOffY = 0.0;
        dX = 0.320; pCol = float3(1.0, 1.0, 1.0); opac = 0.85;
    }

    float4 baseColor = tex2D(ReShade::BackBuffer, texcoord);
    
    if (uShowPlane) 
    {
        float depth = ReShade::GetLinearizedDepth(texcoord);
        float effectiveCenterX = cOffX + (dX * uTargetDepth);
        float2 offset = texcoord - 0.5;
        offset.x -= effectiveCenterX;
        offset.y -= cOffY;
        offset.x *= BUFFER_ASPECT_RATIO;
        float denominator = 1.0 + (rotY * offset.x) + (rotX * offset.y);
        float planeDepth = (denominator > 0.0001) ? (uTargetDepth / denominator) : 99999.0;
        
        float trueHeight = (offset.y - hLvl) * planeDepth;
        float fadeFactor = smoothstep(0.0, 1.0, (trueHeight - wTop) / max(fTop, 0.0001));
        float finalOpacity = opac * fadeFactor;
        
        if (depth > planeDepth && trueHeight >= wTop && trueHeight <= wBot)
        {
            baseColor.rgb = lerp(baseColor.rgb, pCol, finalOpacity);
        }
    }
    
    if (Enable_Overlay)
    {
        float4 overlay = tex2D(Offside_Sampler, texcoord);
        baseColor.rgb = lerp(baseColor.rgb, overlay.rgb, overlay.a);
    }
    
    color = baseColor;
}

technique VAR_Offside_System
{
    pass CombinedPass
    {
        VertexShader = PostProcessVS;
        PixelShader = PS_CombinedOffside;
    }
}