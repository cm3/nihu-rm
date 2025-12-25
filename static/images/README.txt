# アバター画像ディレクトリ

デフォルトのアバター画像を配置する場合：
- ファイル名: avatar-placeholder.png (または .jpg, .svg)
- 推奨サイズ: 140x140ピクセル以上
- 形式: PNG, JPG, SVG

配置後、static/css/style.css の以下の部分を更新してください：

.bl_researcher_avatar_placeholder {
    background-image: url('/static/images/avatar-placeholder.png');
}
