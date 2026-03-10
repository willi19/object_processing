# AutoDex Object Wiki - Project Spec

## 목표
100~1000개 research object들을 브라우징할 수 있는 웹 기반 object wiki.
검색, 카테고리 필터, 3D 뷰어 지원.

## 아키텍처

```
GitHub Pages (willi19.github.io/autodex-wiki)
├── index.html         # 메인 갤러리 페이지 (검색, 필터, 썸네일 그리드)
├── viewer.html        # 3D 뷰어 페이지
├── catalog.json       # object 메타데이터 + HuggingFace URL 매핑
└── js/viewer.js       # Babylon.js 기반 3D 뷰어 로직

HuggingFace Dataset (willi19/autodex-objects)
└── objects/
    └── {object_name}/
        ├── mesh.glb   # OBJ → GLB 변환 (texture 내장)
        └── thumb.png  # 썸네일 (선택)
```

## 파일 포맷
- **소스**: OBJ + MTL + texture PNG 세트
- **배포**: GLB (texture 내장, trimesh로 변환)
- **변환**: `trimesh.load('mesh.obj').export('mesh.glb')`
- OBJ 평균 ~2MB → GLB ~440KB (4배 압축)
- Draco compression 추가 적용 시 더 줄일 수 있음

## 3D 뷰어
- **라이브러리**: Babylon.js (GraspQP 참고)
- **CDN**: `https://cdn.babylonjs.com/babylon.js`
- GLB 로드: `BABYLON.SceneLoader.LoadAssetContainerAsync()`
- Draco decoder: `https://www.gstatic.com/draco/versioned/decoders/1.5.6/`
- mesh는 HuggingFace raw URL로 fetch

## HuggingFace raw URL 형식
```
https://huggingface.co/datasets/willi19/autodex-objects/resolve/main/objects/{name}/mesh.glb
```

## catalog.json 구조 (미정 - 추후 확정)
```json
{
  "objects": [
    {
      "id": "watering_can",
      "label": "Watering Can",
      "category": "container",
      "url": "objects/watering_can/mesh.glb",
      "thumb": "objects/watering_can/thumb.png"
    }
  ]
}
```

## 지원 기능 (예정)
- 이름 검색
- 카테고리 필터
- 3D 인터랙티브 뷰어 (OrbitControl)
- 일괄 다운로드 안내 (`huggingface-cli download`)

## HuggingFace 업로드
```bash
pip install huggingface_hub
huggingface-cli login
huggingface-cli repo create autodex-objects --type dataset
git clone https://huggingface.co/datasets/willi19/autodex-objects
cd autodex-objects
# GLB 파일 복사 후
git add . && git commit -m "add objects" && git push
```

## OBJ → GLB 변환 스크립트 (예정)
- 입력: `objects/{name}/{name}.obj` + `.mtl` + texture
- 출력: `objects/{name}/mesh.glb`
- 자동으로 catalog.json 업데이트

## 참고
- GraspQP 구조 참고: https://graspqp.github.io/static/examples.html
- HuggingFace username: willi19