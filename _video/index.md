---
layout: page
title: Vídeos
permalink: /video/
---
<h1>{{ page.title }}</h1>

Seleção de vídeos do projeto.

O projeto Ciência Aberta Ubatuba produziu diversos vídeos entre 2015 e 2017. Eles foram publicados em dois canais do YouTube:

- [Ciência Aberta Ubatuba](https://www.youtube.com/channel/UC1J2Bd6q6VhFBNGihT2qYvA).
- [CindaLab - Ubatuba](https://www.youtube.com/@CindaLab/search?query=ubatuba).

Abaixo estão alguns destaques.

---

<div class="video-list">
  {% for video_item in site.video reversed %}
    <article class="mb-4 pb-3 border-bottom">
      <h3><a href="{{ video_item.url | relative_url }}">{{ video_item.title }}</a></h3>
      {% if video_item.date %}<p class="text-muted small">Publicado em: {{ video_item.date | date: "%d/%m/%Y" }}</p>{% endif %}
      {{ video_item.excerpt | default: video_item.content | strip_html | truncatewords: 30 }}
       <p><a href="{{ video_item.url | relative_url }}">Assistir vídeo...</a></p>
    </article>
  {% endfor %}
</div>
