import asyncio
import httpx
import pytest
from app.geocoding import PhotonSearch, SearchBusy, SearchUnavailable, normalize_features


def feature(label="Baiterek", point=None):
    return {"geometry":{"type":"Point","coordinates":point or [71.42878,51.1232]},
            "properties":{"name":label,"city":"Astana","country":"Kazakhstan"}}


def test_safe_result_and_duplicate_normalization():
    item=feature('<img src=x onerror=alert(1)>')
    results=normalize_features({"features":[item,item,feature(point=[181,51]),None]})
    assert len(results)==1
    assert results[0]["label"]=='<img src=x onerror=alert(1)>, Astana, Kazakhstan'
    assert results[0]["latitude"]==51.1232


@pytest.mark.parametrize("data", [None, [], {}, {"features":None}])
def test_malformed_response(data):
    with pytest.raises(SearchUnavailable): normalize_features(data)


@pytest.mark.parametrize("point", [[True,51],[float('nan'),51],[71,91],[71],[71,'51']])
def test_invalid_coordinates_are_ignored(point):
    assert normalize_features({"features":[feature(point=point)]})==[]


def test_cache_normalization_expiry_and_capacity():
    async def run():
        calls=[];clock=[0]
        def upstream(request):
            calls.append(request)
            return httpx.Response(200,json={"features":[feature()]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            search=PhotonSearch(client,'https://photon.example/api/',interval=0,ttl=5,max_cache=2,clock=lambda:clock[0])
            first=await search.search(' Baiterek   Astana ','one')
            first[0]['label']='changed by caller'
            second=await search.search('baiterek astana','two')
            assert second[0]['label']!='changed by caller'
            assert len(calls)==1
            assert 'lang' not in calls[0].url.params
            assert calls[0].url.params['bbox']=='70.8,50.8,72.0,51.7'
            clock[0]=6
            await search.search('Baiterek Astana','one')
            assert len(calls)==2
            await search.search('Other query','one');await search.search('Third query','one')
            assert len(search.cache)==2
    asyncio.run(run())


@pytest.mark.parametrize('failure',['timeout','status','malformed','json'])
def test_upstream_errors_are_not_cached(failure):
    async def run():
        def upstream(request):
            if failure=='timeout': raise httpx.ReadTimeout('private endpoint detail',request=request)
            if failure=='status': return httpx.Response(429,json={})
            if failure=='json': return httpx.Response(200,text='not json')
            return httpx.Response(200,json={'bad':'shape'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            search=PhotonSearch(client,'https://photon.example/api/',interval=0)
            with pytest.raises(SearchUnavailable): await search.search('Astana','one')
            assert not search.cache
    asyncio.run(run())


def test_global_busy_and_user_limit():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'features':[]}))) as client:
            search=PhotonSearch(client,'https://photon.example/api/',interval=0)
            await search.lock.acquire()
            with pytest.raises(SearchBusy): await search.search('Astana','one')
            search.lock.release()
            for index in range(10): await search.search(f'Query {index}','one')
            with pytest.raises(SearchBusy): await search.search('New query','one')
            assert await search.search('Query 1','one')==[] # Cache does not use upstream quota.
            assert await search.search('New query','other')==[]
    asyncio.run(run())


def test_request_spacing(monkeypatch):
    async def run():
        sleeps=[]
        async def record_sleep(seconds): sleeps.append(seconds)
        monkeypatch.setattr('app.geocoding.asyncio.sleep',record_sleep)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'features':[]}))) as client:
            search=PhotonSearch(client,'https://photon.example/api/',clock=lambda:0)
            await search.search('First','one');await search.search('Second','one')
            assert sleeps==[1.1]
    asyncio.run(run())
