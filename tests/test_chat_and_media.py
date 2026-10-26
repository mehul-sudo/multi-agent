"""
Tests for Chat Assistant & Media Generation Service.

Verifies conversational streaming, autonomous reasoning fallback,
Flux AI image generation, video simulation keyframe generation,
and endpoint reliability.
"""

import pytest
from app.services.media_generation_service import MediaGenerationService
from app.api.v1.chat import generate_autonomous_response


def test_media_generation_detection():
    # Image triggers
    is_media, media_type, target = MediaGenerationService.detect_media_request("generate an image of a cybernetic tiger")
    assert is_media is True
    assert media_type == "image"
    assert "cybernetic tiger" in target

    is_media, media_type, target = MediaGenerationService.detect_media_request("draw a serene sunset over mountains")
    assert is_media is True
    assert media_type == "image"
    assert "mountains" in target

    # Video triggers
    is_media, media_type, target = MediaGenerationService.detect_media_request("generate a video of an astronaut floating in deep space")
    assert is_media is True
    assert media_type == "video"
    assert "astronaut floating" in target

    # Non-media questions
    is_media, media_type, target = MediaGenerationService.detect_media_request("What is today's date?")
    assert is_media is False


def test_media_generation_image_service():
    res = MediaGenerationService.generate_image("futuristic cyberpunk vehicle", style="cyberpunk", width=512, height=512)
    assert res["success"] is True
    assert res["media_type"] == "image"
    assert "image_url" in res
    assert "https://image.pollinations.ai/prompt/" in res["image_url"]
    assert "model=flux" in res["image_url"]
    assert res["width"] == 512
    assert res["height"] == 512


def test_media_generation_video_service():
    res = MediaGenerationService.generate_video_simulation("drone flying over neon city")
    assert res["success"] is True
    assert res["media_type"] == "video"
    assert "keyframe_url" in res
    assert "16:9" in res["aspect_ratio"]


def test_generate_autonomous_response():
    # Temporal
    time_str = "Monday, October 05, 2026 (12:00 PM UTC)"
    resp = generate_autonomous_response("what is today's date and time?", time_str)
    assert "Verified Temporal Status" in resp
    assert time_str in resp

    # Hindi / Hinglish
    resp_hi = generate_autonomous_response("nhi chal rha re kuch help karo", time_str)
    assert "Namaste" in resp_hi
    assert "AI Image Generation" in resp_hi
    assert "Email Agent" in resp_hi

    # Technical
    resp_tech = generate_autonomous_response("How to write python code for agents?", time_str)
    assert "Technical Architecture" in resp_tech
    assert "from app.agents.registry import get_agent_instance" in resp_tech


def test_chat_generate_image_endpoint(client, auth_headers):
    resp = client.post("/api/v1/chat/generate-image", json={
        "prompt": "hyperrealistic glowing crystal dragon in cavern",
        "style": "3d_render",
        "width": 1024,
        "height": 1024
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "https://image.pollinations.ai/prompt/" in data["image_url"]
    assert data["style"] == "3d_render"


def test_chat_message_image_flow(client, auth_headers):
    resp = client.post("/api/v1/chat", json={
        "message": "generate an image of a high tech quantum computer core",
        "mode": "auto"
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "image" in data
    assert "https://image.pollinations.ai/prompt/" in data["image"]["image_url"]


def test_chat_stream_image_flow(client, auth_headers):
    resp = client.post("/api/v1/chat/stream", json={
        "message": "create a picture of an enchanted forest with fairy lights",
        "mode": "image"
    }, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "assistant.image" in body
    assert "https://image.pollinations.ai/prompt/" in body
