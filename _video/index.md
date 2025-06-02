---
layout: default
title: Vídeos
permalink: /video/
---
<h1>{{ page.title }}</h1>

O projeto Ciência Aberta Ubatuba produziu diversos vídeos entre 2015 e 2017. Eles foram publicados em dois canais do YouTube:

- [Ciência Aberta Ubatuba](https://www.youtube.com/channel/UC1J2Bd6q6VhFBNGihT2qYvA).
- [CindaLab - Ubatuba](https://www.youtube.com/@CindaLab/search?query=ubatuba).


<h2>Destaques</h2>

<div class="video-list">
  {% for video_item in site.video reversed %}
    <article class="mb-4 pb-3 border-bottom">
      {% if video_item.youtube_id %}
      <a href="{{ video_item.url | relative_url }}">
        <img src="https://img.youtube.com/vi/{{ video_item.youtube_id }}/hqdefault.jpg" alt="{{ video_item.title | escape }} thumbnail" class="video-thumbnail">
      </a>
      {% endif %}
      <h3><a href="{{ video_item.url | relative_url }}">{{ video_item.title | escape }}</a></h3>
      {% if video_item.date %}<p class="text-muted small">Publicado em: {{ video_item.date | date: "%d/%m/%Y" }}</p>{% elsif video_item.date_original_string %}<p class="text-muted small">Data: {{ video_item.date_original_string }}</p>{% endif %}
      <div class="content-excerpt">
        {{ video_item.excerpt }}
      </div>
      <p><a href="{{ video_item.url | relative_url }}">Assistir vídeo...</a></p>
    </article>
  {% endfor %}
</div>